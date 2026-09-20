# -*- coding: utf-8 -*-
"""
routers/suggest_router.py
══════════════════════════
Proje Öneri Sistemi REST endpoint'leri.

database_router.py ile aynı pattern:
  - asyncpg pool üzerinden PostgreSQL
  - run_in_executor ile CPU-bound embedding thread'e taşınır
  - SentenceTransformer singleton (_get_model)

Endpoint:
  POST /suggest/search   → üç modun tamamı (title / abstract / fulltext)
  GET  /suggest/health   → servis sağlık kontrolü

main.py'ye eklemek için:
  from routers.suggest_router import router as suggest_router
  app.include_router(suggest_router, prefix="/suggest")
"""

from __future__ import annotations

import asyncio
import threading
import time
from functools import partial
from typing import Optional

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sentence_transformers import SentenceTransformer

# ── Mevcut servisler (değiştirilmedi) ────────────────────────────
from services.auth import get_current_user
from services.text_preprocessing import extract_full_text_from_pdf
from services.upload_validation import validate_pdf_bytes
from services.rate_limit import llm_daily_limit, rate_limit
from services.config import EMBEDDING_MODEL, OPENROUTER_API_KEY

# ── Öneri servisi ─────────────────────────────────────────────────
from services.suggest_service import (
    run_title_search,
    run_abstract_search,
    run_fulltext_search,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Suggest"])

# ── Embedding modeli (database_router ile aynı singleton pattern) ─
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
    """
    Embedding CPU-bound — database_router ile aynı run_in_executor pattern.
    FastAPI event-loop bloklanmaz.
    """
    loop = asyncio.get_running_loop()
    fn   = partial(_get_model().encode, text, normalize_embeddings=True)
    vec  = await loop.run_in_executor(None, fn)
    return vec.tolist()


# ══════════════════════════════════════════════════════════════════
# POST /suggest/search
# ══════════════════════════════════════════════════════════════════

@router.post("/search", dependencies=[Depends(rate_limit), Depends(llm_daily_limit)])
async def suggest_search(
    search_type: str                    = Form(...),   # "title" | "abstract" | "fulltext"
    query_text:  str                    = Form(""),
    top_k:       int                    = Form(12),
    file:        Optional[UploadFile]   = File(None),  # fulltext modunda PDF
    current_user: dict                  = Depends(get_current_user),
):
    """
    Tek endpoint — search_type'a göre ilgili pipeline'ı çağırır.

    Form parametreleri (multipart/form-data):
      search_type : "title" | "abstract" | "fulltext"
      query_text  : kullanıcının girdiği metin (fulltext'te PDF ile birlikte opsiyonel)
      top_k       : kaç sonuç döneceği (varsayılan 12)
      file        : sadece fulltext modunda PDF dosyası (opsiyonel)

    Dönen yapı (Suggest.jsx beklentisi):
    {
      "success": true,
      "total": 8,
      "results": [
        {
          "score": 0.91,
          "pdf_name": "ornek.pdf",
          "raw_title": "Derin Öğrenme ile...",
          "book_name": "BM498",
          "year": 2024,
          "matched_text": "...chunk snippet..."
        }
      ],
      "llm_suggestion": {
        "mode": "text" | "rag",
        "success": true,
        "field": "Makine Öğrenmesi",
        "risk_level": "yüksek|orta|düşük",

        // text modu:
        "analysis": "...",

        // rag modu:
        "similarity_analysis": "...",
        "original_aspects": [...],
        "improvement_suggestions": [...],

        // her iki modda:
        "topic_suggestions": [{title, rationale, novelty_score}],
        "revised_title": "..."
      }
    }
    """
    t0 = time.time()
    user_id = int(current_user["sub"])

    # ── Doğrulama ────────────────────────────────────────────────
    if search_type not in ("title", "abstract", "fulltext"):
        raise HTTPException(
            status_code=422,
            detail="search_type 'title', 'abstract' veya 'fulltext' olmalı",
        )

    # PDF bytes al
    pdf_bytes:    Optional[bytes] = None
    pdf_filename: Optional[str]   = None
    if file and file.filename:
        pdf_bytes    = await file.read()
        validate_pdf_bytes(pdf_bytes, file.filename)
        pdf_filename = file.filename

    # En az bir girdi zorunlu
    clean_text = query_text.strip()
    if not clean_text and not pdf_bytes:
        raise HTTPException(
            status_code=422,
            detail="query_text veya PDF dosyası gerekli",
        )

    # ── Embedding metni belirle ───────────────────────────────────
    # PDF yüklendi ama metin girilmediyse → PDF'den metin çıkar
    embed_text = clean_text
    if pdf_bytes and not embed_text:
        embed_text = extract_full_text_from_pdf(pdf_bytes) or ""
        if not embed_text:
            raise HTTPException(
                status_code=400,
                detail="PDF'den metin çıkarılamadı. Lütfen metin girin.",
            )

    # ── BERT embedding (thread pool) ─────────────────────────────
    query_vec = await _embed_async(embed_text)

    # ── Pipeline ─────────────────────────────────────────────────
    try:
        if search_type == "title":
            result = await run_title_search(
                query_text=embed_text,
                query_vec=query_vec,
                user_id=user_id,
                top_k=top_k,
            )
        elif search_type == "abstract":
            result = await run_abstract_search(
                query_text=embed_text,
                query_vec=query_vec,
                user_id=user_id,
                top_k=top_k,
            )
        else:  # fulltext
            result = await run_fulltext_search(
                query_text=embed_text,
                query_vec=query_vec,
                user_id=user_id,
                top_k=top_k,
                pdf_bytes=pdf_bytes,
            )

    except Exception as exc:
        logger.error("[Suggest] Pipeline hatası: %s", exc)
        raise HTTPException(status_code=500, detail="Öneri işlenirken bir hata oluştu.")

    result["duration_ms"] = int((time.time() - t0) * 1000)
    return result


# ══════════════════════════════════════════════════════════════════
# GET /suggest/health
# ══════════════════════════════════════════════════════════════════

@router.get("/health")
async def suggest_health():
    """Model ve OpenRouter sağlık kontrolü."""
    model_ok      = False
    openrouter_ok = bool(OPENROUTER_API_KEY)

    try:
        _get_model()
        model_ok = True
    except Exception:
        pass

    return {
        "status":        "ok" if (model_ok and openrouter_ok) else "degraded",
        "model_ok":      model_ok,
        "openrouter_ok": openrouter_ok,
    }