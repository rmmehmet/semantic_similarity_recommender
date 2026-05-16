"""
database_router.py
------------------
Veritabanı yönetim sayfasının tüm REST endpoint'leri.

Metin çıkarma : services/text_preprocessing.py  (extract_*)
Chunk işlemi  : services/chunking_service.py     (build_chunk_records)
Embedding     : sentence-transformers            (run_in_executor)
PostgreSQL    : services/database/postgres_service.py
Milvus        : services/database/milvus_service.py
"""

from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path
import os
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

# ── Metin çıkarma (mevcut kod, değiştirilmedi) ───────────────────
from services.text_preprocessing import (
    extract_title_from_pdf,
    extract_abstract_from_pdf,
    extract_full_text_from_pdf,
)

# ── Chunk servisi (yeni ayrı modül) ──────────────────────────────
from services.chunking_service import build_chunk_records

# ── PostgreSQL ───────────────────────────────────────────────────
from services.database.postgres_service import (
    pg_delete_chunks,
    pg_delete_paper,
    pg_get_detail,
    pg_insert_chunks,
    pg_list_papers,
    pg_paper_exists,
    pg_stats,
    pg_truncate_all,
    pg_upsert_paper,
)

# ── Milvus ───────────────────────────────────────────────────────
from services.database.milvus_service import (
    milvus_delete_pdf,
    milvus_drop_all,
    milvus_insert_abstract,
    milvus_insert_fulltext_chunks,
    milvus_insert_title,
    milvus_stats,
)

from services.database.init_milvus import create_all_collections
from sentence_transformers import SentenceTransformer

# ── Router ────────────────────────────────────────────────────────
router = APIRouter(tags=["Database"])

# ── PDF Depolama ─────────────────────────────────────────────────
PDF_STORAGE_DIR = Path(os.getenv("PDF_STORAGE_DIR", "storage/pdfs"))
PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Koleksiyon adları (stats endpoint'inde kullanılır)
COL_TITLES    = "liftup_titles"
COL_ABSTRACTS = "liftup_abstracts"
COL_FULLTEXT  = "liftup_fulltext"

# ── Embedding Modeli (singleton) ─────────────────────────────────
_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


async def _embed_async(texts: list[str]) -> list[list[float]]:
    """
    Embedding işlemi CPU-bound olduğu için ayrı thread'de çalıştırılır.
    FastAPI event-loop'u bloklanmaz.
    """
    loop = asyncio.get_event_loop()
    fn   = partial(_get_model().encode, texts, normalize_embeddings=True)
    vecs = await loop.run_in_executor(None, fn)
    return vecs.tolist()


# ══════════════════════════════════════════════════════════════════
# PDF YÜKLE VE İNDEKSLE
# ══════════════════════════════════════════════════════════════════

@router.post("/add")
async def add_pdf(
    file: UploadFile   = File(...),
    book_name: str     = Form(""),
    year: int          = Form(0),
    force_update: bool = Form(False),
):
    """
    İş akışı:
      1. PDF bytes → diske kaydet  (preview için)
      2. Mevcutluk kontrolü
      3. text_preprocessing.py ile metin çıkar
      4. PostgreSQL upsert
      5. chunking_service.py ile chunk kayıtları üret
      6. PostgreSQL chunks tablosuna yaz
      7. Embed (thread pool)
      8. Milvus'a yaz
    """
    pdf_bytes = await file.read()
    pdf_name  = file.filename or "unknown.pdf"

    # ── 1. Diske kaydet ───────────────────────────────────────────
    disk_path = PDF_STORAGE_DIR / Path(pdf_name).name
    disk_path.write_bytes(pdf_bytes)

    # ── 2. Mevcutluk kontrolü ─────────────────────────────────────
    if not force_update and await pg_paper_exists(pdf_name):
        return {
            "status":   "skipped",
            "pdf_name": pdf_name,
            "reason":   "already_exists",
        }

    # ── 3. Metin çıkarma (text_preprocessing.py) ─────────────────
    # Bu fonksiyonlar senkron ama hızlı; fitz I/O dominant → yeterince hızlı
    title    = extract_title_from_pdf(pdf_bytes)    or ""
    abstract = extract_abstract_from_pdf(pdf_bytes) or ""
    fulltext = extract_full_text_from_pdf(pdf_bytes) or ""

    # ── 4. PostgreSQL upsert ──────────────────────────────────────
    paper_id = await pg_upsert_paper(
        pdf_name  = pdf_name,
        raw_title = title,
        abstract  = abstract,
        fulltext  = fulltext,
        book_name = book_name,
        year      = year,
    )

    # ── 5. Chunk üretimi (chunking_service.py) ────────────────────
    # build_chunk_records:
    #   - title   → tek kayıt, chunk yapılmaz
    #   - abstract → 300-500 kar, tek parça
    #   - fulltext → 850 kar, 100 overlap, sentence-aware
    chunk_records, ft_chunks, abs_chunks = build_chunk_records(
        title, abstract, fulltext
    )

    # ── 6. PostgreSQL chunks tablosuna yaz ───────────────────────
    await pg_delete_chunks(paper_id)          # force_update için temizle
    await pg_insert_chunks(paper_id, chunk_records)

    # ── 7. Embedding (thread pool) ────────────────────────────────
    # Sıra: [title, abstract_chunk_0, ft_chunk_0, ft_chunk_1, ...]
    # Abstract ve fulltext chunk sayısı değişken olabilir.
    embed_inputs: list[str] = [title or ""]

    # Abstract: chunk_abstract tek eleman döndürür ama listeyle çalışıyoruz
    for ch in abs_chunks:
        embed_inputs.append(ch)

    for ch in ft_chunks:
        embed_inputs.append(ch)

    all_vecs = await _embed_async(embed_inputs)

    # Vektörleri ayır
    title_vec    = all_vecs[0]
    abs_start    = 1
    abs_end      = abs_start + len(abs_chunks)
    abstract_vec = all_vecs[abs_start] if abs_chunks else all_vecs[0]  # fallback title vec
    ft_vecs      = all_vecs[abs_end:]  # ft_chunks ile birebir eşleşir

    # ── 8. Milvus upsert (sil + ekle) ────────────────────────────
    milvus_delete_pdf(pdf_name)
    milvus_insert_title(pdf_name, title, title_vec)
    milvus_insert_abstract(pdf_name, abs_chunks[0] if abs_chunks else abstract, abstract_vec)
    if ft_chunks and ft_vecs:
        milvus_insert_fulltext_chunks(pdf_name, ft_chunks, ft_vecs)

    return {
        "status":       "ok",
        "pdf_name":     pdf_name,
        "paper_id":     paper_id,
        "title":        title[:120] + ("…" if len(title) > 120 else ""),
        "chunks":       len(ft_chunks),
        "abstract_len": len(abstract),
        "fulltext_len": len(fulltext),
    }


# ══════════════════════════════════════════════════════════════════
# PDF SİL
# ══════════════════════════════════════════════════════════════════

@router.delete("/remove/{pdf_name:path}")
async def remove_pdf(pdf_name: str):
    """PostgreSQL + Milvus + diskten siler."""
    deleted_pg = await pg_delete_paper(pdf_name)
    milvus_delete_pdf(pdf_name)

    disk_path = PDF_STORAGE_DIR / Path(pdf_name).name
    if disk_path.exists():
        disk_path.unlink()

    if not deleted_pg:
        raise HTTPException(status_code=404, detail="PDF bulunamadı")

    return {"status": "deleted", "pdf_name": pdf_name}


# ══════════════════════════════════════════════════════════════════
# PDF LİSTELE
# ══════════════════════════════════════════════════════════════════

@router.get("/list")
async def list_pdfs(limit: int = 500):
    docs = await pg_list_papers(limit)
    return {"documents": docs}


# ══════════════════════════════════════════════════════════════════
# DETAY
# ══════════════════════════════════════════════════════════════════

@router.get("/detail/{pdf_name:path}")
async def get_detail(pdf_name: str):
    detail = await pg_get_detail(pdf_name)
    if not detail:
        raise HTTPException(status_code=404, detail="PDF bulunamadı")
    return {"detail": detail}


# ══════════════════════════════════════════════════════════════════
# PDF STREAM — önizleme
# ══════════════════════════════════════════════════════════════════

@router.get("/preview/{pdf_name:path}")
async def preview_pdf(pdf_name: str):
    """
    PDF'yi tarayıcıda açmak için stream eder.
    add_pdf sırasında diske kaydedilen dosya okunur.
    Path traversal önlemi: Path(pdf_name).name ile sadece dosya adı alınır.
    """
    safe_name = Path(pdf_name).name
    file_path = PDF_STORAGE_DIR / safe_name

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="PDF diskte bulunamadı. Önce yükleyin.",
        )

    async def iter_file():
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(65536)   # 64 KB
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "Cache-Control":       "private, max-age=3600",
        },
    )


# ══════════════════════════════════════════════════════════════════
# İSTATİSTİKLER
# ══════════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_stats():
    try:
        mv = milvus_stats()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Milvus bağlantı hatası: {exc}")

    pg = await pg_stats()

    return {
        "stats": {
            "unique_pdf_count": pg["unique_pdf_count"],
            "chunks_by_type":   pg["chunks_by_type"],
            "liftup_titles":    mv.get(COL_TITLES,    {}),
            "liftup_abstracts": mv.get(COL_ABSTRACTS, {}),
            "liftup_fulltext":  mv.get(COL_FULLTEXT,  {}),
        }
    }


# ══════════════════════════════════════════════════════════════════
# SIFIRLA
# ══════════════════════════════════════════════════════════════════

@router.post("/reset")
async def reset_database():
    """
    Tüm veritabanını sıfırlar. Geri alınamaz.
    Sıra: PostgreSQL → Milvus drop → Milvus yeniden kur → disk temizle
    """
    await pg_truncate_all()

    try:
        milvus_drop_all()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Milvus drop hatası: {exc}")

    try:
        create_all_collections()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Milvus koleksiyon oluşturma hatası: {exc}")

    for f in PDF_STORAGE_DIR.glob("*.pdf"):
        f.unlink(missing_ok=True)

    return {"status": "reset_complete"}