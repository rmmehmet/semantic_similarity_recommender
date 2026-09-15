# -*- coding: utf-8 -*-
"""
scripts/reembed_all.py
════════════════════════
EMBEDDING_MODEL (services/config.py) değiştiğinde BİR KEZ elle çalıştırılır.

Farklı bir embedding modeli farklı bir vektör uzayı üretir — eski modelle
yazılmış vektörlerle yeni modelin vektörleri karşılaştırılamaz. Bu script:

  1. Postgres'teki TÜM kullanıcıların TÜM paper'larını ve onlara ait
     title/abstract/fulltext chunk'larını okur (PDF dosyalarını tekrar
     işlemeye gerek yok — metin zaten Postgres'te duruyor).
  2. Milvus koleksiyonlarını yeni EMBEDDING_DIM ile düşürüp yeniden oluşturur
     (init_milvus._ensure_collection artık dim değişimini de algılıyor).
  3. Her paper için title/abstract/fulltext'i YENİ modelle yeniden embed
     edip Milvus'a yazar — add_pdf ile birebir aynı yazım şemasını izler.

Kullanım:
    cd backend
    ..\venv\Scripts\python.exe scripts\reembed_all.py

Not: Bu script çalışırken (ve tamamlanana kadar) arama/sohbet özellikleri
boş/eksik sonuç döner — koleksiyonlar drop edilip yeniden dolduruluyor.
Trafiği düşük bir zamanda çalıştırın.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s — %(message)s")
logger = logging.getLogger("reembed_all")

BATCH_SIZE = 32  # tek encode() çağrısında gömülecek metin sayısı


async def main() -> None:
    from services.config import EMBEDDING_MODEL, EMBEDDING_DIM
    from services.database.postgres_service import get_pool
    from services.database.init_milvus import create_all_collections
    from services.database.milvus_service import (
        milvus_insert_title,
        milvus_insert_abstract,
        milvus_insert_fulltext_chunks,
        milvus_flush,
        COL_TITLES,
        COL_ABSTRACTS,
        COL_FULLTEXT,
    )
    from sentence_transformers import SentenceTransformer

    logger.info("Embedding modeli: %s (dim=%d)", EMBEDDING_MODEL, EMBEDDING_DIM)
    model = SentenceTransformer(EMBEDDING_MODEL)

    def embed(texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return model.encode(texts, normalize_embeddings=True, batch_size=BATCH_SIZE).tolist()

    pool = await get_pool()
    async with pool.acquire() as conn:
        papers = await conn.fetch(
            "SELECT id, user_id, pdf_name, raw_title, abstract FROM papers ORDER BY id"
        )

    logger.info("%d paper bulundu — Milvus koleksiyonları yeniden oluşturuluyor…", len(papers))
    create_all_collections()  # dim değişmişse eski koleksiyonları drop edip yeniden yaratır

    t0 = time.time()
    ok = 0
    failed: list[str] = []

    for i, paper in enumerate(papers, start=1):
        pdf_name = paper["pdf_name"]
        user_id  = paper["user_id"]
        title    = paper["raw_title"] or ""
        abstract = paper["abstract"] or ""

        try:
            async with pool.acquire() as conn:
                abs_rows = await conn.fetch(
                    "SELECT chunk_text FROM chunks WHERE paper_id = $1 AND chunk_type = 'abstract' ORDER BY chunk_idx",
                    paper["id"],
                )
                ft_rows = await conn.fetch(
                    "SELECT chunk_text FROM chunks WHERE paper_id = $1 AND chunk_type = 'fulltext' ORDER BY chunk_idx",
                    paper["id"],
                )
            abs_chunks = [r["chunk_text"] for r in abs_rows] or ([abstract] if abstract else [])
            ft_chunks  = [r["chunk_text"] for r in ft_rows]

            embed_inputs = [title] + abs_chunks + ft_chunks
            all_vecs = embed(embed_inputs)

            title_vec    = all_vecs[0]
            abs_end      = 1 + len(abs_chunks)
            abstract_vec = all_vecs[1] if abs_chunks else all_vecs[0]
            ft_vecs      = all_vecs[abs_end:]

            milvus_insert_title(pdf_name, title, title_vec, user_id, flush=False)
            milvus_insert_abstract(
                pdf_name, abs_chunks[0] if abs_chunks else abstract, abstract_vec, user_id, flush=False,
            )
            if ft_chunks and ft_vecs:
                milvus_insert_fulltext_chunks(pdf_name, ft_chunks, ft_vecs, user_id, flush=False)

            ok += 1
            if i % 20 == 0 or i == len(papers):
                logger.info("… %d/%d işlendi", i, len(papers))

        except Exception as exc:
            logger.error("BAŞARISIZ — %s (user=%s): %s", pdf_name, user_id, exc)
            failed.append(pdf_name)

    logger.info("Koleksiyonlar flush ediliyor…")
    for col in (COL_TITLES, COL_ABSTRACTS, COL_FULLTEXT):
        milvus_flush(col)

    elapsed = time.time() - t0
    logger.info(
        "Tamamlandı — %d/%d başarılı, %.1fs. Başarısız: %s",
        ok, len(papers), elapsed, failed or "yok",
    )


if __name__ == "__main__":
    asyncio.run(main())
