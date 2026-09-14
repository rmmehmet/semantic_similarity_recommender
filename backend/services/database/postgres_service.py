from __future__ import annotations

import logging
import os
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

_pool: Optional[asyncpg.Pool] = None
_pool_lock = None  # lazily created — see get_pool()


async def get_pool() -> asyncpg.Pool:
    global _pool, _pool_lock
    if _pool is not None:
        return _pool

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL ortam değişkeni tanımlı değil. "
            "Production'da varsayılan/örnek bir bağlantı dizesi kullanılmaz — "
            "lütfen DATABASE_URL değişkenini ayarlayın."
        )

    import asyncio
    if _pool_lock is None:
        _pool_lock = asyncio.Lock()

    async with _pool_lock:
        if _pool is None:
            _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ══════════════════════════════════════════════════════════════════
# PAPERS
# ══════════════════════════════════════════════════════════════════

async def pg_upsert_paper(
    pdf_name: str,
    raw_title: str,
    abstract: str,
    fulltext: str,
    book_name: str = "",
    year: int = 0,
) -> int:
    """
    INSERT OR UPDATE — milvus_synced FALSE olarak başlar.
    Milvus yazımı tamamlandıktan sonra pg_mark_synced() çağrılmalıdır.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO papers
                (pdf_name, raw_title, abstract, fulltext, book_name, year, milvus_synced)
            VALUES ($1, $2, $3, $4, $5, $6, FALSE)
            ON CONFLICT (pdf_name) DO UPDATE
                SET raw_title     = EXCLUDED.raw_title,
                    abstract      = EXCLUDED.abstract,
                    fulltext      = EXCLUDED.fulltext,
                    book_name     = EXCLUDED.book_name,
                    year          = EXCLUDED.year,
                    milvus_synced = FALSE,
                    updated_at    = NOW()
            RETURNING id
            """,
            pdf_name, raw_title, abstract, fulltext, book_name, year,
        )
        return int(row["id"])


async def pg_mark_synced(pdf_name: str) -> None:
    """
    Milvus yazımı başarıyla tamamlandığında çağrılır.
    milvus_synced = TRUE yapar.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE papers SET milvus_synced = TRUE, updated_at = NOW() WHERE pdf_name = $1",
            pdf_name,
        )
    logger.info("[PG] milvus_synced=TRUE — %s", pdf_name)


async def pg_get_unsynced() -> list[dict]:
    """
    milvus_synced=FALSE olan tüm kayıtları döner.
    Reconcile işlemi bu listeyi kullanır.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, pdf_name, raw_title, book_name, year, created_at
            FROM   papers
            WHERE  milvus_synced = FALSE
            ORDER  BY created_at DESC
            """
        )
        return [dict(r) for r in rows]


async def pg_get_paper(pdf_name: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM papers WHERE pdf_name = $1", pdf_name
        )
        return dict(row) if row else None


async def pg_get_papers_by_names(pdf_names: list[str]) -> dict[str, dict]:
    """
    N+1 sorununu çözer — tek sorguda birden fazla paper getirir.
    Dönen dict: { pdf_name → paper_dict }
    """
    if not pdf_names:
        return {}
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, pdf_name, raw_title, book_name, year
            FROM   papers
            WHERE  pdf_name = ANY($1::text[])
            """,
            pdf_names,
        )
        return {r["pdf_name"]: dict(r) for r in rows}


async def pg_list_papers(limit: int = 500) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                pdf_name,
                raw_title,
                book_name,
                year,
                milvus_synced,
                created_at,
                COALESCE(char_length(abstract), 0)::int AS abstract_len,
                COALESCE(char_length(fulltext),  0)::int AS fulltext_len
            FROM papers
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        result = []
        for r in rows:
            d = dict(r)
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            result.append(d)
        return result


async def pg_delete_paper(pdf_name: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM papers WHERE pdf_name = $1", pdf_name
        )
        return result.split()[-1] != "0"


async def pg_paper_exists(pdf_name: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM papers WHERE pdf_name = $1", pdf_name
        )
        return row is not None


async def pg_get_all_pdf_names() -> set[str]:
    """Reconcile için PG'deki tüm pdf_name setini döner."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT pdf_name FROM papers")
        return {r["pdf_name"] for r in rows}


# ══════════════════════════════════════════════════════════════════
# CHUNKS
# ══════════════════════════════════════════════════════════════════

async def pg_insert_chunks(paper_id: int, chunks: list[dict]) -> None:
    if not chunks:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO chunks (paper_id, chunk_text, chunk_idx, chunk_type)
            VALUES ($1, $2, $3, $4)
            """,
            [
                (paper_id, c["chunk_text"], c["chunk_idx"], c["chunk_type"])
                for c in chunks
            ],
        )


async def pg_delete_chunks(paper_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chunks WHERE paper_id = $1", paper_id)


async def pg_get_chunks(
    paper_id: int,
    chunk_type: str = "fulltext",
) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT chunk_idx, chunk_text, chunk_type
            FROM   chunks
            WHERE  paper_id = $1 AND chunk_type = $2
            ORDER  BY chunk_idx
            """,
            paper_id, chunk_type,
        )
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# DETAIL
# ══════════════════════════════════════════════════════════════════

async def pg_get_detail(pdf_name: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM papers WHERE pdf_name = $1", pdf_name
        )
        if not row:
            return None

        paper = dict(row)
        if paper.get("created_at"):
            paper["created_at"] = str(paper["created_at"])
        if paper.get("updated_at"):
            paper["updated_at"] = str(paper["updated_at"])

        chunks = await conn.fetch(
            """
            SELECT chunk_idx, chunk_text, chunk_type
            FROM   chunks
            WHERE  paper_id = $1
            ORDER  BY chunk_type, chunk_idx
            """,
            paper["id"],
        )
        paper["chunks"] = [dict(c) for c in chunks]
        return paper


# ══════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════

async def pg_stats() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        paper_count   = await conn.fetchval("SELECT COUNT(*) FROM papers")
        unsynced_count = await conn.fetchval(
            "SELECT COUNT(*) FROM papers WHERE milvus_synced = FALSE"
        )
        chunk_rows = await conn.fetch(
            """
            SELECT chunk_type, COUNT(*) AS cnt
            FROM   chunks
            GROUP  BY chunk_type
            """
        )
    return {
        "unique_pdf_count":  int(paper_count),
        "unsynced_count":    int(unsynced_count),   # hayalet vektör adayları
        "chunks_by_type":    {r["chunk_type"]: int(r["cnt"]) for r in chunk_rows},
    }


# ══════════════════════════════════════════════════════════════════
# TRUNCATE
# ══════════════════════════════════════════════════════════════════

async def pg_truncate_all() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            TRUNCATE chunks, keywords, suggestions, searches
            RESTART IDENTITY CASCADE
            """
        )
        await conn.execute(
            "TRUNCATE papers RESTART IDENTITY CASCADE"
        )