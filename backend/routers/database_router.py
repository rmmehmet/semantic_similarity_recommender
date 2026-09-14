from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
from functools import partial
from pathlib import Path
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from services.auth import require_admin
from services.upload_validation import read_and_validate_pdf
from services.text_preprocessing import (
    extract_title_from_pdf,
    extract_abstract_from_pdf,
    extract_full_text_from_pdf,
)
from services.chunking_service import build_chunk_records
from services.database.postgres_service import (
    pg_delete_chunks,
    pg_delete_paper,
    pg_get_detail,
    pg_get_paper_by_hash,
    pg_get_unsynced,
    pg_get_all_pdf_names,
    pg_insert_chunks,
    pg_list_papers,
    pg_mark_synced,
    pg_paper_exists,
    pg_stats,
    pg_truncate_all,
    pg_upsert_paper,
)
from services.database.milvus_service import (
    milvus_delete_pdf,
    milvus_drop_all,
    milvus_flush,
    milvus_get_all_pdf_names,
    milvus_insert_abstract,
    milvus_insert_fulltext_chunks,
    milvus_insert_title,
    milvus_stats,
)
from services.database.init_milvus import create_all_collections
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Database"])

PDF_STORAGE_DIR = Path(os.getenv("PDF_STORAGE_DIR", "storage/pdfs"))
PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

COL_TITLES    = "liftup_titles"
COL_ABSTRACTS = "liftup_abstracts"
COL_FULLTEXT  = "liftup_fulltext"

_model: Optional[SentenceTransformer] = None
_model_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


async def _embed_async(texts: list[str]) -> list[list[float]]:
    loop = asyncio.get_running_loop()
    fn   = partial(_get_model().encode, texts, normalize_embeddings=True)
    vecs = await loop.run_in_executor(None, fn)
    return vecs.tolist()


async def _run_blocking(fn, *args, **kwargs):
    """Senkron (bloklayan) Milvus/IO çağrılarını thread pool'a taşır."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(fn, *args, **kwargs))


# ══════════════════════════════════════════════════════════════════
# PDF YÜKLE
# ══════════════════════════════════════════════════════════════════

@router.post("/add", dependencies=[Depends(require_admin)])
async def add_pdf(
    file: UploadFile   = File(...),
    book_name: str     = Form(""),
    year: int          = Form(0),
    force_update: bool = Form(False),
):
    pdf_bytes = await read_and_validate_pdf(file)
    pdf_name  = file.filename or "unknown.pdf"

    # İçerik hash'i — dosya adından bağımsız gerçek tekilleştirme anahtarı.
    # "Aynı isim farklı içerik" ve "farklı isim aynı içerik" senaryolarını
    # ayırt edebilmek için pdf_name yerine (veya onunla birlikte) kullanılır.
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()

    existed  = await pg_paper_exists(pdf_name)
    hash_dup = await pg_get_paper_by_hash(content_hash)

    if hash_dup and hash_dup["pdf_name"] != pdf_name:
        # Aynı içerik, farklı bir isim altında zaten yüklenmiş.
        # force_update bile bunu atlamamalı — amaç BU ismi güncellemek,
        # başka bir isim altında duplicate oluşturmak değil.
        return {
            "status":           "duplicate_content",
            "pdf_name":         pdf_name,
            "matched_pdf_name": hash_dup["pdf_name"],
            "reason": (
                f"Bu belge içerik olarak zaten '{hash_dup['pdf_name']}' "
                f"adıyla yüklenmiş."
            ),
        }

    if existed and not hash_dup and not force_update:
        # Aynı isim var ama içerik hash'i eşleşmiyor — bu, isim çakışan
        # FARKLI bir belge. Sessizce atlamak veri kaybına/karışıklığa yol
        # açar; kullanıcı force_update ile bilinçli olarak üzerine yazmalı.
        return {
            "status": "name_conflict",
            "pdf_name": pdf_name,
            "reason": (
                "Bu isimde farklı içerikli bir belge zaten kayıtlı. "
                "Üzerine yazmak için 'force_update' seçeneğini kullanın "
                "ya da dosyayı farklı bir adla yükleyin."
            ),
        }

    if not force_update and existed and hash_dup:
        # Aynı isim + aynı içerik → gerçek bir tam eşleşme, işe yaramaz tekrar işleme.
        return {"status": "skipped", "pdf_name": pdf_name, "reason": "already_exists"}

    disk_path = PDF_STORAGE_DIR / Path(pdf_name).name
    disk_path.write_bytes(pdf_bytes)

    # Diskten sonraki adımlardan biri beklenmedik şekilde patlarsa (extraction,
    # Postgres yazımı), diskte DB kaydı olmayan "yetim" bir dosya kalmasın —
    # bu bloktaki her hatada diske yazılan dosyayı geri temizliyoruz.
    try:
        title    = extract_title_from_pdf(pdf_bytes)    or ""
        abstract = extract_abstract_from_pdf(pdf_bytes) or ""
        fulltext = extract_full_text_from_pdf(pdf_bytes) or ""

        # milvus_synced=FALSE olarak başlar
        paper_id = await pg_upsert_paper(
            pdf_name=pdf_name, raw_title=title, abstract=abstract,
            fulltext=fulltext, book_name=book_name, year=year,
            content_hash=content_hash,
        )

        chunk_records, ft_chunks, abs_chunks = build_chunk_records(title, abstract, fulltext)
        await pg_delete_chunks(paper_id)
        await pg_insert_chunks(paper_id, chunk_records)
    except Exception as exc:
        logger.error("[Add] İşleme hatası — %s: %s", pdf_name, exc)
        disk_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="PDF işlenirken bir hata oluştu.")

    embed_inputs = [title or ""]
    for ch in abs_chunks:
        embed_inputs.append(ch)
    for ch in ft_chunks:
        embed_inputs.append(ch)

    all_vecs = await _embed_async(embed_inputs)

    title_vec    = all_vecs[0]
    abs_start    = 1
    abs_end      = abs_start + len(abs_chunks)
    abstract_vec = all_vecs[abs_start] if abs_chunks else all_vecs[0]
    ft_vecs      = all_vecs[abs_end:]

    # Milvus yazımı — hata olursa milvus_synced FALSE kalır, loglanır
    #
    # Performans notu: col.flush() pahalı, senkron bir Milvus RPC'sidir.
    # Eskiden bu blok PDF başına 6 kez flush çağırıyordu (3 silme + 3 ekleme),
    # bunların hepsi sırayla bekleniyordu — yükleme süresini ciddi şekilde
    # şişiriyordu. Artık:
    #   1) Silme sadece gerçekten var olan bir kayıt güncelleniyorsa yapılır
    #      (yeni PDF'lerde gereksiz 3 silme+flush RPC'si tamamen atlanır).
    #   2) 3 insert paralel çalışır (ayrı koleksiyonlar, birbirini bloklamaz).
    #   3) flush tek seferde, sonunda ve paralel yapılır.
    try:
        if existed:
            await _run_blocking(milvus_delete_pdf, pdf_name, False)  # flush=False

        insert_tasks = [
            _run_blocking(milvus_insert_title, pdf_name, title, title_vec, False),
            _run_blocking(
                milvus_insert_abstract,
                pdf_name, abs_chunks[0] if abs_chunks else abstract, abstract_vec, False,
            ),
        ]
        if ft_chunks and ft_vecs:
            insert_tasks.append(
                _run_blocking(milvus_insert_fulltext_chunks, pdf_name, ft_chunks, ft_vecs, False)
            )
        await asyncio.gather(*insert_tasks)

        flush_targets = [COL_TITLES, COL_ABSTRACTS]
        if ft_chunks and ft_vecs:
            flush_targets.append(COL_FULLTEXT)
        await asyncio.gather(*(_run_blocking(milvus_flush, name) for name in flush_targets))

        # Başarılıysa senkronize olarak işaretle
        await pg_mark_synced(pdf_name)
        milvus_ok = True

    except Exception as exc:
        logger.error("[Milvus] Yazım hatası — %s: %s", pdf_name, exc)
        milvus_ok = False

    return {
        "status":       "ok" if milvus_ok else "partial",
        "pdf_name":     pdf_name,
        "paper_id":     paper_id,
        "milvus_synced": milvus_ok,
        "title":        title[:120] + ("…" if len(title) > 120 else ""),
        "chunks":       len(ft_chunks),
        "abstract_len": len(abstract),
        "fulltext_len": len(fulltext),
    }


# ══════════════════════════════════════════════════════════════════
# PDF SİL
# ══════════════════════════════════════════════════════════════════

@router.delete("/remove/{pdf_name:path}", dependencies=[Depends(require_admin)])
async def remove_pdf(pdf_name: str):
    deleted_pg = await pg_delete_paper(pdf_name)
    if not deleted_pg:
        raise HTTPException(status_code=404, detail="PDF bulunamadı")

    # Milvus silme — başarısız olursa logla ama 500 verme
    # (PG zaten silindi, reconcile ile Milvus temizlenir)
    try:
        await _run_blocking(milvus_delete_pdf, pdf_name)
    except Exception as exc:
        logger.error("[Milvus] Silme hatası — %s: %s", pdf_name, exc)

    disk_path = PDF_STORAGE_DIR / Path(pdf_name).name
    if disk_path.exists():
        disk_path.unlink()

    return {"status": "deleted", "pdf_name": pdf_name}


# ══════════════════════════════════════════════════════════════════
# LİSTELE
# ══════════════════════════════════════════════════════════════════

MAX_LIST_LIMIT = 1000


@router.get("/list")
async def list_pdfs(limit: int = 500):
    limit = max(1, min(limit, MAX_LIST_LIMIT))
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
# PDF STREAM
# ══════════════════════════════════════════════════════════════════

@router.get("/preview/{pdf_name:path}")
async def preview_pdf(pdf_name: str):
    safe_name = Path(pdf_name).name
    file_path = PDF_STORAGE_DIR / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="PDF diskte bulunamadı.")

    async def iter_file():
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(65536)
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
        mv = await _run_blocking(milvus_stats)
    except Exception as exc:
        logger.error("[Stats] Milvus bağlantı hatası: %s", exc)
        raise HTTPException(status_code=503, detail="Milvus bağlantı hatası")

    pg = await pg_stats()

    return {
        "stats": {
            "unique_pdf_count":  pg["unique_pdf_count"],
            "unsynced_count":    pg["unsynced_count"],    # hayalet vektör adayı
            "chunks_by_type":    pg["chunks_by_type"],
            "liftup_titles":     mv.get(COL_TITLES,    {}),
            "liftup_abstracts":  mv.get(COL_ABSTRACTS, {}),
            "liftup_fulltext":   mv.get(COL_FULLTEXT,  {}),
        }
    }


# ══════════════════════════════════════════════════════════════════
# RECONCILE  —  PG ↔ Milvus tutarsızlıklarını tespit et ve düzelt
# POST /database/reconcile
# ══════════════════════════════════════════════════════════════════

@router.post("/reconcile", dependencies=[Depends(require_admin)])
async def reconcile_database():
    """
    İki yönlü tutarsızlık kontrolü:

    1. PG'de milvus_synced=FALSE olanlar
       → Milvus'ta kontrol et, eksikse yeniden embed + yaz

    2. Milvus'taki pdf_name'ler PG'de yoksa
       → Hayalet vektör → Milvus'tan sil

    Döner:
      fixed_unsynced  : PG'de FALSE → Milvus'a yazıldı
      ghost_removed   : Milvus'ta var, PG'de yok → silindi
      errors          : düzeltilemeyenler
    """
    result = {
        "fixed_unsynced": [],
        "ghost_removed":  [],
        "errors":         [],
    }

    # ── 1. PG'de milvus_synced=FALSE olanları düzelt ─────────────
    unsynced = await pg_get_unsynced()
    if unsynced:
        logger.info("[Reconcile] %d adet senkronize olmayan kayıt bulundu.", len(unsynced))

    for record in unsynced:
        pdf_name = record["pdf_name"]
        try:
            # PG'den tam metinleri çek
            from services.database.postgres_service import pg_get_paper, pg_get_chunks
            paper = await pg_get_paper(pdf_name)
            if not paper:
                result["errors"].append({"pdf_name": pdf_name, "reason": "PG kaydı bulunamadı"})
                continue

            title    = paper.get("raw_title") or ""
            abstract = paper.get("abstract")  or ""
            fulltext = paper.get("fulltext")  or ""

            # Chunk'ları yeniden oluştur ve embed et
            from services.chunking_service import build_chunk_records
            _, ft_chunks, abs_chunks = build_chunk_records(title, abstract, fulltext)

            embed_inputs = [title or ""]
            for ch in abs_chunks:
                embed_inputs.append(ch)
            for ch in ft_chunks:
                embed_inputs.append(ch)

            all_vecs = await _embed_async(embed_inputs)

            title_vec    = all_vecs[0]
            abs_start    = 1
            abs_end      = abs_start + len(abs_chunks)
            abstract_vec = all_vecs[abs_start] if abs_chunks else all_vecs[0]
            ft_vecs      = all_vecs[abs_end:]

            # Bu kayıt milvus_synced=FALSE olduğu için Milvus'ta eksik/yarım
            # veri olabilir — silme burada gerçekten gerekli. Ama yine de
            # flush'ı erteleyip sonda paralel yapıyoruz (bkz. add_pdf).
            await _run_blocking(milvus_delete_pdf, pdf_name, False)

            insert_tasks = [
                _run_blocking(milvus_insert_title, pdf_name, title, title_vec, False),
                _run_blocking(
                    milvus_insert_abstract,
                    pdf_name, abs_chunks[0] if abs_chunks else abstract, abstract_vec, False,
                ),
            ]
            if ft_chunks and ft_vecs:
                insert_tasks.append(
                    _run_blocking(milvus_insert_fulltext_chunks, pdf_name, ft_chunks, ft_vecs, False)
                )
            await asyncio.gather(*insert_tasks)

            flush_targets = [COL_TITLES, COL_ABSTRACTS]
            if ft_chunks and ft_vecs:
                flush_targets.append(COL_FULLTEXT)
            await asyncio.gather(*(_run_blocking(milvus_flush, name) for name in flush_targets))

            await pg_mark_synced(pdf_name)
            result["fixed_unsynced"].append(pdf_name)
            logger.info("[Reconcile] Düzeltildi: %s", pdf_name)

        except Exception as exc:
            logger.error("[Reconcile] Hata — %s: %s", pdf_name, exc)
            result["errors"].append({"pdf_name": pdf_name, "reason": str(exc)})

    # ── 2. Milvus'ta var, PG'de yok → hayalet vektör sil ─────────
    try:
        milvus_names = await _run_blocking(milvus_get_all_pdf_names)
        pg_names = await pg_get_all_pdf_names()

        ghosts = milvus_names - pg_names
        if ghosts:
            logger.warning("[Reconcile] %d hayalet vektör bulundu.", len(ghosts))

        for ghost in ghosts:
            try:
                await _run_blocking(milvus_delete_pdf, ghost)
                result["ghost_removed"].append(ghost)
                logger.info("[Reconcile] Hayalet silindi: %s", ghost)
            except Exception as exc:
                logger.error("[Reconcile] Hayalet silinemedi — %s: %s", ghost, exc)
                result["errors"].append({"pdf_name": ghost, "reason": str(exc)})

    except Exception as exc:
        logger.error("[Reconcile] Milvus sorgu hatası: %s", exc)
        result["errors"].append({"pdf_name": "__milvus_query__", "reason": str(exc)})

    result["summary"] = {
        "fixed":   len(result["fixed_unsynced"]),
        "ghosts":  len(result["ghost_removed"]),
        "errors":  len(result["errors"]),
        "clean":   len(result["errors"]) == 0,
    }

    logger.info("[Reconcile] Tamamlandı: %s", result["summary"])
    return result


# ══════════════════════════════════════════════════════════════════
# SIFIRLA
# ══════════════════════════════════════════════════════════════════

@router.post("/reset", dependencies=[Depends(require_admin)])
async def reset_database():
    await pg_truncate_all()

    try:
        await _run_blocking(milvus_drop_all)
    except Exception as exc:
        logger.error("[Reset] Milvus drop hatası: %s", exc)
        raise HTTPException(status_code=500, detail="Milvus drop hatası")

    try:
        await _run_blocking(create_all_collections)
    except Exception as exc:
        logger.error("[Reset] Milvus koleksiyon hatası: %s", exc)
        raise HTTPException(status_code=500, detail="Milvus koleksiyon hatası")

    for f in PDF_STORAGE_DIR.glob("*.pdf"):
        f.unlink(missing_ok=True)

    return {"status": "reset_complete"}