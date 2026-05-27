# -*- coding: utf-8 -*-
"""
services/suggest_service.py
════════════════════════════
Üç arama modunun (title / abstract / fulltext) iş akışını yönetir.

Her mod kendi Milvus koleksiyonunu kullanır — hibrit skor yok.
  title    → liftup_titles    : Milvus COSINE skoru direkt kullanılır
  abstract → liftup_abstracts : Milvus COSINE skoru direkt kullanılır
  fulltext → liftup_fulltext  : chunk araması → paper bazında max-pooling → COSINE skoru

Milvus koleksiyonları (init_milvus.py şeması):
  liftup_titles    → pdf_name | text | vector
  liftup_abstracts → pdf_name | text | vector
  liftup_fulltext  → pdf_name | chunk_idx | text | vector

Kullanılan mevcut servisler (değiştirilmedi):
  milvus_service.py   → milvus_search()
  postgres_service.py → pg_get_paper(), pg_get_chunks()
  text_preprocessing  → extract_full_text_from_pdf()
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import List, Dict, Optional, Any

from sentence_transformers import SentenceTransformer

# ── Mevcut servisler ──────────────────────────────────────────────
from services.database.milvus_service import milvus_search
from services.database.postgres_service import pg_get_paper, pg_get_chunks
from services.text_preprocessing import extract_full_text_from_pdf

# ── LLM servisi ───────────────────────────────────────────────────
from services.llm.llm_suggestion_service import (
    generate_topic_suggestion,
    generate_rag_analysis,
)

# ── Sabitler ──────────────────────────────────────────────────────
COL_TITLES    = "liftup_titles"
COL_ABSTRACTS = "liftup_abstracts"
COL_FULLTEXT  = "liftup_fulltext"

TITLE_FIELDS    = ["pdf_name", "text"]
ABSTRACT_FIELDS = ["pdf_name", "text"]
FULLTEXT_FIELDS = ["pdf_name", "chunk_idx", "text"]

# ── Singleton BERT modeli ─────────────────────────────────────────
_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


def _embed_sync(text: str) -> List[float]:
    return _get_model().encode(text, normalize_embeddings=True).tolist()


async def _embed_async(text: str) -> List[float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_embed_sync, text))


# ══════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ══════════════════════════════════════════════════════════════════

def _snippet(text: str, max_len: int = 200) -> str:
    return (text or "")[:max_len]


def _normalize_hit(h: Dict, matched_text: str = "") -> Dict:
    """
    Milvus hit'ini Suggest.jsx ResultCard formatına çevirir.
    init_milvus.py'de başlık alanı adı "text" olduğu için raw_title'a map edilir.
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
    Milvus sonuçlarına PostgreSQL'den book_name, year, raw_title ekler.
    pg_get_paper → mevcut postgres_service fonksiyonu.
    """
    for item in items:
        try:
            paper = await pg_get_paper(item["pdf_name"])
            if paper:
                item["book_name"] = paper.get("book_name", "")
                item["year"]      = paper.get("year", 0)
                if not item.get("raw_title"):
                    item["raw_title"] = paper.get("raw_title", "")
        except Exception:
            pass
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
    liftup_titles koleksiyonunda COSINE benzerlik araması.
    Skor: direkt Milvus COSINE skoru.
    LLM: text modu (generate_topic_suggestion).
    """
    raw_hits = milvus_search(
        collection_name=COL_TITLES,
        query_vector=query_vec,
        top_k=top_k,
        output_fields=TITLE_FIELDS,
    )

    results: List[Dict] = []
    for h in raw_hits:
        item = _normalize_hit(h, matched_text="")
        results.append(item)

    results = await _enrich_pg(results)

    loop = asyncio.get_event_loop()
    llm  = await loop.run_in_executor(
        None,
        partial(generate_topic_suggestion, query_text, "title", results),
    )

    return {
        "success":        True,
        "total":          len(results),
        "results":        results,
        "llm_suggestion": llm,
    }


# ══════════════════════════════════════════════════════════════════
# ABSTRACT ARAMA
# ══════════════════════════════════════════════════════════════════

async def run_abstract_search(
    query_text: str,
    query_vec:  List[float],
    top_k:      int = 12,
) -> Dict[str, Any]:
    """
    liftup_abstracts koleksiyonunda COSINE benzerlik araması.
    Skor: direkt Milvus COSINE skoru.
    matched_text: özet chunk'ının ilk 200 karakteri.
    LLM: text modu (generate_topic_suggestion).
    """
    raw_hits = milvus_search(
        collection_name=COL_ABSTRACTS,
        query_vector=query_vec,
        top_k=top_k,
        output_fields=ABSTRACT_FIELDS,
    )

    # Aynı PDF birden fazla chunk dönebilir — paper başına ilk (en yüksek) tut
    seen: set = set()
    results: List[Dict] = []
    for h in raw_hits:
        pdf_name = h.get("pdf_name", "")
        if pdf_name in seen:
            continue
        seen.add(pdf_name)

        snippet = _snippet(h.get("text", ""))
        item    = _normalize_hit(h, matched_text=snippet)
        results.append(item)

    results = await _enrich_pg(results)

    loop = asyncio.get_event_loop()
    llm  = await loop.run_in_executor(
        None,
        partial(generate_topic_suggestion, query_text, "abstract", results),
    )

    return {
        "success":        True,
        "total":          len(results),
        "results":        results,
        "llm_suggestion": llm,
    }


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
    liftup_fulltext koleksiyonunda chunk bazlı COSINE araması.

    Skor:
      - Her PDF için en yüksek chunk skorunu tut (max-pooling).
      - Hibrit formül yok — Milvus COSINE skoru direkt kullanılır.

    RAG:
      - Top chunk'lar + PostgreSQL chunk'ları → LLM context.
      - PDF yüklendiyse tam metin RAG prompt'una eklenir.
    LLM: RAG modu (generate_rag_analysis).
    """
    # 1. Chunk araması — top_k * 4 al, paper başına max-pooling yapacağız
    raw_hits = milvus_search(
        collection_name=COL_FULLTEXT,
        query_vector=query_vec,
        top_k=top_k * 4,
        output_fields=FULLTEXT_FIELDS,
    )

    # 2. Paper bazında max-pooling — en yüksek chunk skoru o paperi temsil eder
    best_by_pdf: Dict[str, Dict] = {}
    for h in raw_hits:
        pdf_name = h.get("pdf_name", "")
        score    = float(h.get("score", 0.0))
        if pdf_name not in best_by_pdf or score > best_by_pdf[pdf_name]["score"]:
            best_by_pdf[pdf_name] = h

    # 3. Sonuç listesi — skoru direkt Milvus COSINE
    results: List[Dict] = []
    for pdf_name, h in best_by_pdf.items():
        snippet = _snippet(h.get("text", ""))
        item    = _normalize_hit(h, matched_text=snippet)
        item["raw_title"] = ""   # _enrich_pg dolduracak
        results.append(item)

    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:top_k]
    results = await _enrich_pg(results)

    # 4. RAG context builder
    # a) Milvus'tan gelen ham chunk'lar (en alakalı 20)
    rag_context: List[Dict] = []
    for h in raw_hits[:20]:
        rag_context.append({
            "matched_text": _snippet(h.get("text", "")),
            "raw_title":    h.get("pdf_name", ""),
            "score":        float(h.get("score", 0.0)),
        })

    # b) PostgreSQL'den üst 3 paperin tam chunk'ları → daha zengin context
    for r in results[:3]:
        try:
            paper = await pg_get_paper(r["pdf_name"])
            if paper:
                pg_chunks = await pg_get_chunks(paper["id"], chunk_type="fulltext")
                for c in pg_chunks[:4]:
                    rag_context.append({
                        "matched_text": _snippet(c.get("chunk_text", "")),
                        "raw_title":    paper.get("raw_title", r["pdf_name"]),
                        "score":        r["score"],
                    })
        except Exception:
            pass

    # c) results listesine rag_context'i de ekle (generate_rag_analysis
    #    "similar_projects" parametresindeki matched_text'i kullanır)
    for i, r in enumerate(results):
        if not r.get("matched_text") and i < len(rag_context):
            r["matched_text"] = rag_context[i].get("matched_text", "")

    # 5. PDF tam metni
    pdf_full_text = query_text
    if pdf_bytes:
        pdf_full_text = extract_full_text_from_pdf(pdf_bytes) or query_text

    pdf_title = results[0].get("raw_title", "") if results else ""

    # 6. RAG + LLM (blocking → thread pool)
    loop = asyncio.get_event_loop()
    llm  = await loop.run_in_executor(
        None,
        partial(generate_rag_analysis, pdf_full_text, pdf_title, results),
    )

    return {
        "success":        True,
        "total":          len(results),
        "results":        results,
        "llm_suggestion": llm,
    }