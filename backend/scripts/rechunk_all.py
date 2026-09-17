# -*- coding: utf-8 -*-
"""
scripts/rechunk_all.py
════════════════════════
chunking_service.py'de bir mantık değişikliği yapıldığında (örn. section
tespiti, referans bölümü hariç tutma, cümle bölme kuralları) BİR KEZ elle
çalıştırılır.

scripts/reembed_all.py'den farkı: o script sadece Postgres'te ZATEN var olan
chunk satırlarını yeniden embed eder, metni yeniden CHUNKLAMAZ — bu yüzden
section-aware chunking gibi bir özellik eklendiğinde, o özellikten önce
yüklenmiş belgelerin chunk'ları (section/subsection/page_start/page_end,
referans bölümü hariç tutma vb.) eskisi gibi kalır. Bu script bunu düzeltir:

  1. Postgres'teki TÜM kullanıcıların TÜM paper'larını okur (title/abstract/
     fulltext zaten Postgres'te duruyor — PDF dosyalarını tekrar işlemeye
     gerek yok).
  2. Her paper için chunking_service.build_chunk_records()'ı YENİDEN çağırır
     — güncel section/referans/cümle-bölme kurallarıyla.
  3. Postgres `chunks` tablosundaki eski satırları silip yenileriyle
     değiştirir (routers/database_router.py::reconcile bunu YAPMAZ — sadece
     Milvus'u tazeler, Postgres chunk metadata'sını eski bırakır).
  4. Yeni chunk'ları yeniden embed edip Milvus'a yazar (add_pdf ile aynı
     yazım şeması, mevcut vektörlerin üzerine).

Kullanım:
    cd backend
    ..\\venv\\Scripts\\python.exe scripts\\rechunk_all.py [--dry-run]

Not: Bu script çalışırken (ve tamamlanana kadar) arama/sohbet özellikleri
etkilenen belgeler için eksik/tutarsız sonuç dönebilir. Trafiği düşük bir
zamanda çalıştırın.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s — %(message)s")
logger = logging.getLogger("rechunk_all")

BATCH_SIZE = 32  # tek encode() çağrısında gömülecek metin sayısı


async def main(dry_run: bool) -> None:
    from services.chunking_service import build_chunk_records
    from services.database.postgres_service import (
        get_pool,
        pg_delete_chunks,
        pg_insert_chunks,
        pg_mark_synced,
    )
    from services.database.milvus_service import (
        milvus_delete_pdf,
        milvus_insert_title,
        milvus_insert_abstract,
        milvus_insert_fulltext_chunks,
        milvus_flush,
        COL_TITLES,
        COL_ABSTRACTS,
        COL_FULLTEXT,
    )
    from sentence_transformers import SentenceTransformer
    from services.config import EMBEDDING_MODEL

    logger.info("Embedding modeli: %s", EMBEDDING_MODEL)
    model = SentenceTransformer(EMBEDDING_MODEL)

    def embed(texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return model.encode(texts, normalize_embeddings=True, batch_size=BATCH_SIZE).tolist()

    pool = await get_pool()
    async with pool.acquire() as conn:
        papers = await conn.fetch(
            "SELECT id, user_id, pdf_name, raw_title, abstract, fulltext FROM papers ORDER BY id"
        )

    logger.info("%d paper bulundu.%s", len(papers), " (DRY RUN — hiçbir şey yazılmayacak)" if dry_run else "")

    t0 = time.time()
    ok = 0
    changed = 0
    failed: list[str] = []

    for i, paper in enumerate(papers, start=1):
        paper_id = paper["id"]
        pdf_name = paper["pdf_name"]
        user_id  = paper["user_id"]
        title    = paper["raw_title"] or ""
        abstract = paper["abstract"]  or ""
        fulltext = paper["fulltext"]  or ""

        try:
            async with pool.acquire() as conn:
                old_ft_count = await conn.fetchval(
                    "SELECT count(*) FROM chunks WHERE paper_id = $1 AND chunk_type = 'fulltext'",
                    paper_id,
                )

            chunk_records, ft_chunks, abs_chunks = build_chunk_records(title, abstract, fulltext)

            if len(ft_chunks) != old_ft_count:
                changed += 1
                logger.info(
                    "  %s: fulltext chunk sayısı %d → %d (section filtresi/cümle bölme farklı sonuç verdi)",
                    pdf_name, old_ft_count, len(ft_chunks),
                )

            if dry_run:
                ok += 1
                continue

            await pg_delete_chunks(paper_id)
            await pg_insert_chunks(paper_id, chunk_records)

            embed_inputs = [title] + abs_chunks + [c["text"] for c in ft_chunks]
            all_vecs = embed(embed_inputs)

            title_vec    = all_vecs[0]
            abs_end      = 1 + len(abs_chunks)
            abstract_vec = all_vecs[1] if abs_chunks else all_vecs[0]
            ft_vecs      = all_vecs[abs_end:]

            await asyncio.get_running_loop().run_in_executor(
                None, milvus_delete_pdf, pdf_name, user_id, False
            )
            milvus_insert_title(pdf_name, title, title_vec, user_id, flush=False)
            milvus_insert_abstract(
                pdf_name, abs_chunks[0] if abs_chunks else abstract, abstract_vec, user_id, flush=False,
            )
            if ft_chunks and ft_vecs:
                milvus_insert_fulltext_chunks(pdf_name, ft_chunks, ft_vecs, user_id, flush=False)

            await pg_mark_synced(pdf_name, user_id)
            ok += 1

            if i % 20 == 0 or i == len(papers):
                logger.info("… %d/%d işlendi", i, len(papers))

        except Exception as exc:
            logger.error("BAŞARISIZ — %s (user=%s): %s", pdf_name, user_id, exc)
            failed.append(pdf_name)

    if not dry_run:
        logger.info("Koleksiyonlar flush ediliyor…")
        for col in (COL_TITLES, COL_ABSTRACTS, COL_FULLTEXT):
            milvus_flush(col)

    elapsed = time.time() - t0
    logger.info(
        "Tamamlandı — %d/%d başarılı, %d belgede chunk sayısı değişti, %.1fs. Başarısız: %s",
        ok, len(papers), changed, elapsed, failed or "yok",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Hiçbir şey yazmadan, hangi belgelerde chunk sayısının değişeceğini raporla.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
