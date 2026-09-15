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
from services.database.postgres_service import pg_get_papers_by_names, pg_get_recent_messages
from services.llm.chat_llm_service import call_ollama_chat, ollama_available

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


async def run_chat(
    user_id: int,
    message: str,
    pdf_names: list[str],
    conversation_id: Optional[int],
) -> dict[str, Any]:
    if not ollama_available():
        return {
            "success": False,
            "reply": "Ollama şu anda erişilebilir değil. Lütfen daha sonra tekrar deneyin.",
            "sources": [],
        }

    query_vec = await _embed_async(message)

    top_k = min(MAX_TOP_K, TOP_K_PER_DOC * len(pdf_names)) if pdf_names else TOP_K_GENERAL
    expr = _build_expr(user_id, pdf_names)

    try:
        raw_hits = await _milvus_search_async(
            collection_name=COL_FULLTEXT,
            query_vector=query_vec,
            top_k=top_k,
            output_fields=["pdf_name", "chunk_idx", "text"],
            expr=expr,
        )
    except Exception as exc:
        logger.error("[Chat] Milvus arama hatası (user=%s): %s", user_id, exc)
        raw_hits = []

    # Başlık zenginleştirme (kaynak gösterimi için)
    hit_pdf_names = list({h.get("pdf_name", "") for h in raw_hits if h.get("pdf_name")})
    papers = await pg_get_papers_by_names(hit_pdf_names, user_id) if hit_pdf_names else {}

    context_blocks: list[str] = []
    sources: list[dict] = []
    seen_pdfs: set[str] = set()
    for h in sorted(raw_hits, key=lambda x: -float(x.get("score", 0))):
        pname = h.get("pdf_name", "")
        text  = h.get("text", "")
        if not pname or not text:
            continue
        context_blocks.append(f"[{pname}] {text}")
        if pname not in seen_pdfs:
            seen_pdfs.add(pname)
            title = (papers.get(pname) or {}).get("raw_title") or pname
            sources.append({
                "pdf_name":  pname,
                "raw_title": title,
                "score":     round(float(h.get("score", 0)), 4),
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

    loop = asyncio.get_running_loop()
    try:
        reply = await loop.run_in_executor(None, partial(call_ollama_chat, messages))
    except Exception as exc:
        logger.error("[Chat] Ollama çağrı hatası (user=%s): %s", user_id, exc)
        return {"success": False, "reply": "Yanıt üretilirken bir hata oluştu.", "sources": []}

    return {"success": True, "reply": reply, "sources": sources}
