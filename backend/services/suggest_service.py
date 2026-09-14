# -*- coding: utf-8 -*-
"""
services/suggest_service.py
════════════════════════════
Üç arama modunun (title / abstract / fulltext) iş akışını yönetir.

Her mod kendi Milvus koleksiyonunu kullanır — hibrit skor yok.
  title    → liftup_titles    : Milvus COSINE skoru direkt
  abstract → liftup_abstracts : Milvus COSINE skoru direkt
  fulltext → liftup_fulltext  : chunk araması → max-pooling → COSINE skoru

Değişiklikler:
  - _enrich_pg → pg_get_papers_by_names (tek sorgu, N+1 fix)
  - PostgreSQL chunk çekme korundu (RAG context için)
  - Magic number'lar sabit olarak tanımlandı
  - Loglama eklendi
"""

from __future__ import annotations

import asyncio
import logging
import threading
from functools import partial
from typing import List, Dict, Optional, Any

from sentence_transformers import SentenceTransformer

from services.database.milvus_service import milvus_search
from services.database.postgres_service import (
    pg_get_paper,
    pg_get_papers_by_names,
    pg_get_chunks,
)
from services.text_preprocessing import extract_full_text_from_pdf
from services.llm.llm_suggestion_service import (
    generate_topic_suggestion,
    generate_rag_analysis,
)

logger = logging.getLogger(__name__)

# ── Koleksiyon adları ─────────────────────────────────────────────
COL_TITLES    = "liftup_titles"
COL_ABSTRACTS = "liftup_abstracts"
COL_FULLTEXT  = "liftup_fulltext"

TITLE_FIELDS    = ["pdf_name", "text"]
ABSTRACT_FIELDS = ["pdf_name", "text"]
FULLTEXT_FIELDS = ["pdf_name", "chunk_idx", "text"]

# ── Sabitler ──────────────────────────────────────────────────────
CHUNK_FETCH_MULTIPLIER  = 4   # top_k * 4 chunk getirilir, max-pooling sonrası top_k kalır
RAG_MILVUS_CHUNK_LIMIT  = 20  # Milvus'tan RAG context için alınan ham chunk sayısı
RAG_PG_TOP_PAPERS       = 3   # PostgreSQL'den chunk çekilecek üst paper sayısı
RAG_PG_CHUNKS_PER_PAPER = 4   # Her paper için PG'den alınacak chunk sayısı

# ── Singleton BERT modeli ─────────────────────────────────────────
_model: Optional[SentenceTransformer] = None
_model_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


def _embed_sync(text: str) -> List[float]:
    return _get_model().encode(text, normalize_embeddings=True).tolist()


async def _embed_async(text: str) -> List[float]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_embed_sync, text))


async def _milvus_search_async(*args, **kwargs):
    """milvus_search senkron/bloklayan bir çağrıdır — thread pool'a taşınır."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(milvus_search, *args, **kwargs))


# ══════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ══════════════════════════════════════════════════════════════════

def _snippet(text: str, max_len: int = 200) -> str:
    return (text or "")[:max_len]


def _normalize_hit(h: Dict, matched_text: str = "") -> Dict:
    """
    Milvus hit'ini Suggest.jsx ResultCard formatına çevirir.
    init_milvus.py şemasında başlık alanı "text" olarak geçiyor.
    """
    return {
        "score":        round(float(h.get("score", 0.0)), 6),
        "pdf_name":     h.get("pdf_name", ""),
        "raw_title":    h.get("text", h.get("pdf_name", "")),
        "book_name":    "",   # _enrich_pg ile doldurulacak
        "year":         0,    # _enrich_pg ile doldurulacak
        "matched_text": matched_text,
    }


async def _enrich_pg(items: List[Dict]) -> List[Dict]:
    """
    N+1 fix: tüm pdf_name'leri tek PG sorgusunda çeker.
    pg_get_papers_by_names → WHERE pdf_name = ANY($1::text[])
    """
    if not items:
        return items

    pdf_names = [item["pdf_name"] for item in items]
    papers    = await pg_get_papers_by_names(pdf_names)

    for item in items:
        paper = papers.get(item["pdf_name"])
        if paper:
            item["book_name"] = paper.get("book_name", "")
            item["year"]      = paper.get("year", 0)
            if not item.get("raw_title"):
                item["raw_title"] = paper.get("raw_title", "")

    return items


# ══════════════════════════════════════════════════════════════════
# TITLE ARAMA
# ══════════════════════════════════════════════════════════════════

async def run_title_search(
    query_text: str,
    query_vec:  List[float],
    top_k:      int = 12,
) -> Dict[str, Any]:
    """
    liftup_titles → COSINE → text-mod LLM öneri
    """
    logger.info("[Suggest/title] başladı — top_k=%d", top_k)

    raw_hits = await _milvus_search_async(
        collection_name=COL_TITLES,
        query_vector=query_vec,
        top_k=top_k,
        output_fields=TITLE_FIELDS,
    )

    results: List[Dict] = [_normalize_hit(h) for h in raw_hits]
    results = await _enrich_pg(results)

    loop = asyncio.get_running_loop()
    llm  = await loop.run_in_executor(
        None,
        partial(generate_topic_suggestion, query_text, "title", results),
    )

    logger.info("[Suggest/title] tamamlandı — %d sonuç", len(results))
    return {"success": True, "total": len(results), "results": results, "llm_suggestion": llm}


# ══════════════════════════════════════════════════════════════════
# ABSTRACT ARAMA
# ══════════════════════════════════════════════════════════════════

async def run_abstract_search(
    query_text: str,
    query_vec:  List[float],
    top_k:      int = 12,
) -> Dict[str, Any]:
    """
    liftup_abstracts → COSINE → paper başına tekilleştirme → text-mod LLM
    """
    logger.info("[Suggest/abstract] başladı — top_k=%d", top_k)

    raw_hits = await _milvus_search_async(
        collection_name=COL_ABSTRACTS,
        query_vector=query_vec,
        top_k=top_k,
        output_fields=ABSTRACT_FIELDS,
    )

    # Paper başına en yüksek skoru tut (abstract'ta tek chunk var ama
    # ileride multi-chunk olursa da güvenli çalışır)
    seen:    set        = set()
    results: List[Dict] = []
    for h in raw_hits:
        pdf_name = h.get("pdf_name", "")
        if pdf_name in seen:
            continue
        seen.add(pdf_name)
        results.append(_normalize_hit(h, matched_text=_snippet(h.get("text", ""))))

    results = await _enrich_pg(results)

    loop = asyncio.get_running_loop()
    llm  = await loop.run_in_executor(
        None,
        partial(generate_topic_suggestion, query_text, "abstract", results),
    )

    logger.info("[Suggest/abstract] tamamlandı — %d sonuç", len(results))
    return {"success": True, "total": len(results), "results": results, "llm_suggestion": llm}


# ══════════════════════════════════════════════════════════════════
# FULLTEXT ARAMA + RAG
# ══════════════════════════════════════════════════════════════════

async def run_fulltext_search(
    query_text: str,
    query_vec:  List[float],
    top_k:      int = 12,
    pdf_bytes:  Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    liftup_fulltext chunk araması → max-pooling → RAG context → LLM

    RAG context iki kaynaktan beslenir:
      a) Milvus'tan gelen ham chunk'lar (hızlı, semantik)
      b) PostgreSQL'deki tam chunk kayıtları (zengin, tam metin)
    """
    logger.info("[Suggest/fulltext] başladı — top_k=%d", top_k)

    # ── 1. Chunk araması ──────────────────────────────────────────
    raw_hits = await _milvus_search_async(
        collection_name=COL_FULLTEXT,
        query_vector=query_vec,
        top_k=top_k * CHUNK_FETCH_MULTIPLIER,
        output_fields=FULLTEXT_FIELDS,
    )

    # ── 2. Paper bazında max-pooling ──────────────────────────────
    best_by_pdf: Dict[str, Dict] = {}
    for h in raw_hits:
        pdf_name = h.get("pdf_name", "")
        score    = float(h.get("score", 0.0))
        if pdf_name not in best_by_pdf or score > best_by_pdf[pdf_name]["score"]:
            best_by_pdf[pdf_name] = h

    # ── 3. Sonuç listesi ─────────────────────────────────────────
    results: List[Dict] = []
    for pdf_name, h in best_by_pdf.items():
        item = _normalize_hit(h, matched_text=_snippet(h.get("text", "")))
        item["raw_title"] = ""   # _enrich_pg dolduracak
        results.append(item)

    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:top_k]
    results = await _enrich_pg(results)   # tek PG sorgusu — N+1 yok

    # ── 4. RAG context builder ────────────────────────────────────

    # 4a) Milvus ham chunk'ları — semantik olarak en alakalı
    for h in raw_hits[:RAG_MILVUS_CHUNK_LIMIT]:
        pname = h.get("pdf_name", "")
        # matched_text henüz boşsa ham chunk snippet'i kullan
        for r in results:
            if r["pdf_name"] == pname and not r.get("matched_text"):
                r["matched_text"] = _snippet(h.get("text", ""))
                break

    # 4b) PostgreSQL'den üst N paperin tam chunk'ları
    #     Milvus'un göremediği bağlamsal bilgiyi tamamlar
    for r in results[:RAG_PG_TOP_PAPERS]:
        try:
            paper = await pg_get_paper(r["pdf_name"])
            if not paper:
                continue
            pg_chunks = await pg_get_chunks(
                paper["id"], chunk_type="fulltext"
            )
            # matched_text yoksa PG'den ilk chunk'ı kullan
            if not r.get("matched_text") and pg_chunks:
                r["matched_text"] = _snippet(pg_chunks[0].get("chunk_text", ""))

            # PG chunk'larını result'a ekle (LLM context için)
            r["pg_chunks"] = [
                c.get("chunk_text", "")
                for c in pg_chunks[:RAG_PG_CHUNKS_PER_PAPER]
            ]
        except Exception as exc:
            logger.warning(
                "[Suggest/fulltext] PG chunk çekme hatası — %s: %s",
                r["pdf_name"], exc,
            )

    # ── 5. PDF tam metni ─────────────────────────────────────────
    pdf_full_text = query_text
    if pdf_bytes:
        extracted = extract_full_text_from_pdf(pdf_bytes) or query_text
        pdf_full_text = extracted
        logger.info(
            "[Suggest/fulltext] PDF tam metni çıkarıldı — %d karakter",
            len(pdf_full_text),
        )

    pdf_title = results[0].get("raw_title", "") if results else ""

    # ── 6. RAG + LLM ─────────────────────────────────────────────
    loop = asyncio.get_running_loop()
    llm  = await loop.run_in_executor(
        None,
        partial(generate_rag_analysis, pdf_full_text, pdf_title, results),
    )

    logger.info("[Suggest/fulltext] tamamlandı — %d sonuç", len(results))
    return {"success": True, "total": len(results), "results": results, "llm_suggestion": llm}