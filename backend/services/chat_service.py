# -*- coding: utf-8 -*-
"""
services/chat_service.py
═══════════════════════════
"PDF Sohbet" özelliğinin RAG (retrieval-augmented) orkestrasyonu.

Akış:
  1. Kullanıcının mesajı embed edilir (BERT).
  2. liftup_fulltext koleksiyonunda, SADECE bu kullanıcının belgeleri
     içinde (user_id filtreli) — belirli PDF'ler seçilmişse ayrıca
     pdf_name filtreli — en alakalı chunk'lar aranır.
  3. Bulunan chunk'lar + konuşma geçmişi + yeni soru ile Ollama'ya
     bir sohbet isteği gönderilir, serbest metin yanıt alınır.

PDF seçilmemişse (genel mod): arama kullanıcının TÜM belgelerinde yapılır
— "bana X hakkındaki projeleri getir" gibi sorular için.
PDF seçilmişse: arama sadece o belge(ler)in chunk'larıyla sınırlanır.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from functools import partial
from typing import Any, Optional

from sentence_transformers import SentenceTransformer

from services.config import EMBEDDING_MODEL
from services.database.milvus_service import milvus_search
from services.database.postgres_service import (
    pg_get_papers_by_names,
    pg_get_recent_messages,
    pg_keyword_search_chunks,
)
from services.hybrid_search import fuse_hits
from services.llm.chat_llm_service import call_ollama_chat, ollama_available, stream_ollama_chat
from services.llm.reranker import rerank

logger = logging.getLogger(__name__)

COL_FULLTEXT = "liftup_fulltext"

TOP_K_GENERAL   = 8    # PDF seçilmemişse (tüm kütüphanede arama)
TOP_K_PER_DOC   = 4    # seçilen her PDF için alınacak chunk sayısı
MAX_TOP_K       = 24
MAX_HISTORY_TURNS = 10

SYSTEM_PROMPT = (
    "Sen AltayAI'nin belge sohbet asistanısın. Kullanıcının kendi yüklediği "
    "PDF belgelerinden (akademik proje/bildiri) alınan alıntılara dayanarak "
    "sorularını yanıtlarsın. SADECE sağlanan bağlamdaki bilgiyi kullan; "
    "bağlamda cevap yoksa bunu açıkça söyle, asla uydurma. Türkçe, net ve "
    "öz yanıt ver. Hangi belgeden alıntı yaptığını, belge adını belirterek söyle."
)

_model: Optional[SentenceTransformer] = None
_model_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


async def _embed_async(text: str) -> list[float]:
    loop = asyncio.get_running_loop()
    fn   = partial(_get_model().encode, text, normalize_embeddings=True)
    vec  = await loop.run_in_executor(None, fn)
    return vec.tolist()


async def _milvus_search_async(*args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(milvus_search, *args, **kwargs))


def _safe_name(name: str) -> str:
    return name.replace('"', "").replace("'", "").replace("\\", "")


def _build_expr(user_id: int, pdf_names: list[str]) -> str:
    expr = f"user_id == {int(user_id)}"
    if pdf_names:
        quoted = ", ".join(f'"{_safe_name(n)}"' for n in pdf_names)
        expr += f" && pdf_name in [{quoted}]"
    return expr


async def _prepare_messages(
    user_id: int,
    message: str,
    pdf_names: list[str],
    conversation_id: Optional[int],
) -> tuple[list[dict], list[dict]]:
    """
    Ortak hazırlık adımı: embed → Milvus arama → context/kaynak listesi →
    history → tam mesaj listesi. Hem run_chat (tek seferlik) hem stream_chat
    (parça parça) tarafından kullanılır — LLM'e SADECE bu fonksiyonun çıktısı
    farklı şekillerde gönderilir, retrieval mantığı tek yerde kalır.

    Döner: (messages, sources)
    """
    query_vec = await _embed_async(message)

    top_k = min(MAX_TOP_K, TOP_K_PER_DOC * len(pdf_names)) if pdf_names else TOP_K_GENERAL
    expr = _build_expr(user_id, pdf_names)

    # Hibrit arama — vektör (Milvus) + anahtar kelime (Postgres), paralel
    # çalışır, RRF ile birleştirilir (bkz. services/hybrid_search.py).
    # İkisi de best-effort: biri hata verirse diğeriyle devam edilir.
    async def _vector_search() -> list[dict]:
        try:
            return await _milvus_search_async(
                collection_name=COL_FULLTEXT,
                query_vector=query_vec,
                top_k=top_k,
                output_fields=["pdf_name", "chunk_idx", "text", "section", "subsection", "page_start", "page_end"],
                expr=expr,
            )
        except Exception as exc:
            logger.error("[Chat] Milvus arama hatası (user=%s): %s", user_id, exc)
            return []

    async def _keyword_search() -> list[dict]:
        try:
            return await pg_keyword_search_chunks(user_id, message, pdf_names=pdf_names or None, limit=top_k)
        except Exception as exc:
            logger.warning("[Chat] Anahtar kelime arama hatası (user=%s): %s", user_id, exc)
            return []

    vector_hits, keyword_hits = await asyncio.gather(_vector_search(), _keyword_search())
    raw_hits = fuse_hits(vector_hits, keyword_hits)

    # Reranking — embedding skorunun ıskaladığı gerçek alakayı LLM'e sorup
    # düzeltir. Başarısız/kapalıysa orijinal (Milvus skor) sırası korunur.
    if raw_hits:
        loop_r = asyncio.get_running_loop()
        order = await loop_r.run_in_executor(
            None, partial(rerank, message, [h.get("text", "") for h in raw_hits]),
        )
        raw_hits = [raw_hits[i] for i in order]

    # Başlık zenginleştirme (kaynak gösterimi için)
    hit_pdf_names = list({h.get("pdf_name", "") for h in raw_hits if h.get("pdf_name")})
    papers = await pg_get_papers_by_names(hit_pdf_names, user_id) if hit_pdf_names else {}

    context_blocks: list[str] = []
    sources: list[dict] = []
    seen_pdfs: set[str] = set()
    for h in raw_hits:
        pname = h.get("pdf_name", "")
        text  = h.get("text", "")
        if not pname or not text:
            continue

        section    = h.get("section") or ""
        subsection = h.get("subsection") or ""
        location_bits = []
        if section:
            location_bits.append(section + (f" > {subsection}" if subsection else ""))
        if h.get("page_start"):
            pages = str(h["page_start"])
            if h.get("page_end") and h["page_end"] != h["page_start"]:
                pages += f"–{h['page_end']}"
            location_bits.append(f"s.{pages}")
        location = f" ({', '.join(location_bits)})" if location_bits else ""

        context_blocks.append(f"[{pname}{location}] {text}")
        if pname not in seen_pdfs:
            seen_pdfs.add(pname)
            title = (papers.get(pname) or {}).get("raw_title") or pname
            sources.append({
                "pdf_name":  pname,
                "raw_title": title,
                "score":     round(float(h.get("score", 0)), 4),
                "section":   section,
            })

    context = "\n\n".join(context_blocks) if context_blocks else "— İlgili bir alıntı bulunamadı —"

    history = await pg_get_recent_messages(conversation_id, MAX_HISTORY_TURNS) if conversation_id else []

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history:
        role    = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({
        "role": "user",
        "content": f"Belgelerden alınan bağlam:\n{context}\n\nSoru: {message}",
    })

    return messages, sources


async def run_chat(
    user_id: int,
    message: str,
    pdf_names: list[str],
    conversation_id: Optional[int],
) -> dict[str, Any]:
    if not ollama_available():
        return {
            "success": False,
            "reply": "OpenRouter şu anda erişilebilir değil. Lütfen daha sonra tekrar deneyin.",
            "sources": [],
        }

    messages, sources = await _prepare_messages(user_id, message, pdf_names, conversation_id)

    loop = asyncio.get_running_loop()
    try:
        reply = await loop.run_in_executor(None, partial(call_ollama_chat, messages))
    except Exception as exc:
        logger.error("[Chat] OpenRouter çağrı hatası (user=%s): %s", user_id, exc)
        return {"success": False, "reply": "Yanıt üretilirken bir hata oluştu.", "sources": []}

    return {"success": True, "reply": reply, "sources": sources}


async def stream_chat(
    user_id: int,
    message: str,
    pdf_names: list[str],
    conversation_id: Optional[int],
):
    """
    run_chat ile aynı retrieval/prompt hazırlığını yapar, ama LLM yanıtını
    parça parça yield eder. Her öğe bir dict:
      {"type": "chunk", "delta": str}
      {"type": "done",  "reply": str, "sources": [...]}
      {"type": "error", "message": str}
    "done"/"error" ile biter — çağıran taraf (chat_router.py) bundan sonra
    Postgres'e yazma/response sonlandırma işini yapar.
    """
    if not ollama_available():
        yield {
            "type": "error",
            "message": "OpenRouter şu anda erişilebilir değil. Lütfen daha sonra tekrar deneyin.",
        }
        return

    messages, sources = await _prepare_messages(user_id, message, pdf_names, conversation_id)

    loop  = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()

    def worker() -> None:
        try:
            for delta in stream_ollama_chat(messages):
                loop.call_soon_threadsafe(queue.put_nowait, delta)
        except Exception as exc:  # noqa: BLE001 — hata tipini queue üzerinden taşımak için yakalanır
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

    loop.run_in_executor(None, worker)

    full_reply: list[str] = []
    while True:
        item = await queue.get()
        if item is _SENTINEL:
            break
        if isinstance(item, Exception):
            logger.error("[Chat] OpenRouter akış hatası (user=%s): %s", user_id, item)
            yield {"type": "error", "message": "Yanıt üretilirken bir hata oluştu."}
            return
        full_reply.append(item)
        yield {"type": "chunk", "delta": item}

    yield {"type": "done", "reply": "".join(full_reply), "sources": sources}
