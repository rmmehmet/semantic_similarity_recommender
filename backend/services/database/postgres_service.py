from __future__ import annotations

import os
from typing import Optional

import asyncpg

# ── Connection ──────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:123@localhost:5432/liftup_db",
)

_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    """Returns a singleton asyncpg connection pool. If the pool doesn't exist yet, it will be created with the specified DATABASE_URL. Subsequent calls will return the same pool instance.
    Returns:
        asyncpg.Pool: The singleton asyncpg connection pool.
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool

async def close_pool() -> None:
    """ Closes the asyncpg connection pool if it exists. After calling this function, the pool will be set to None, and a new pool will be created on the next call to get_pool().
    Returns:
        None
    """
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
    """INSERT OR UPDATE"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO papers (pdf_name, raw_title, abstract, fulltext, book_name, year)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (pdf_name) DO UPDATE
                SET raw_title  = EXCLUDED.raw_title,
                    abstract   = EXCLUDED.abstract,
                    fulltext   = EXCLUDED.fulltext,
                    book_name  = EXCLUDED.book_name,
                    year       = EXCLUDED.year,
                    updated_at = NOW()
            RETURNING id
            """,
            pdf_name, raw_title, abstract, fulltext, book_name, year,
        )
        return int(row["id"])

async def pg_get_paper(pdf_name: str) -> Optional[dict]:
    """Returns the paper record with the given pdf_name, or None if not found. The returned dictionary includes all fields from the papers table, with created_at and updated_at converted to strings for JSON serialization.
    Parameters:
        pdf_name (str): The name of the PDF file to retrieve.
    Returns:
        Optional[dict]: The paper record as a dictionary, or None if not found.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM papers WHERE pdf_name = $1", pdf_name
        )
        return dict(row) if row else None

async def pg_list_papers(limit: int = 500) -> list[dict]:
    """Lists papers with optional limit.
    Parameters:
        limit (int): The maximum number of papers to return. Defaults to 500.
    Returns:
        list[dict]: A list of paper records as dictionaries.
    """
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
                created_at,
                COALESCE(char_length(abstract), 0)::int  AS abstract_len,
                COALESCE(char_length(fulltext), 0)::int  AS fulltext_len
            FROM papers
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        result = []
        for r in rows:
            d = dict(r)
            # asyncpg datetime → str 
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            result.append(d)
        return result

async def pg_delete_paper(pdf_name: str) -> bool:
    """Deletes the paper with the given pdf_name. Returns True if a paper was deleted, False if no paper with that name was found.
    Parameters:
        pdf_name (str): The name of the PDF file to delete.
    Returns:
        bool: True if a paper was deleted, False if no paper with that name was found.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM papers WHERE pdf_name = $1", pdf_name
        )
        # result: "DELETE N"
        return result.split()[-1] != "0"

async def pg_paper_exists(pdf_name: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM papers WHERE pdf_name = $1", pdf_name
        )
        return row is not None

# ══════════════════════════════════════════════════════════════════
# CHUNKS
# ══════════════════════════════════════════════════════════════════

async def pg_insert_chunks(paper_id: int, chunks: list[dict]) -> None:
    """
    chunks: [{"chunk_text": str, "chunk_idx": int, "chunk_type": str}]
    chunk_type: 'title' | 'abstract' | 'fulltext'

    DÜZELTME: ON CONFLICT DO NOTHING yerine INSERT ... IF NOT EXISTS.
    chunks tablosunda (paper_id, chunk_idx, chunk_type) üzerine unique
    constraint eklenirse ON CONFLICT kullanılabilir; şimdilik silip tekrar
    eklemek daha güvenli (pg_delete_chunks çağrısı önceden yapılmalı).
    """
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
    """Deletes all chunks associated with the given paper_id. This should be called before re-inserting chunks for a paper to ensure that old chunks are removed.
    Parameters:
        paper_id (int): The ID of the paper for which to delete chunks.
    Returns:
        None
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chunks WHERE paper_id = $1", paper_id)

async def pg_get_chunks(
    paper_id: int,
    chunk_type: str = "fulltext",
) -> list[dict]:
    """Returns a list of chunks for the given paper_id and chunk_type, ordered by chunk_idx. Each chunk is returned as a dictionary with keys 'chunk_idx', 'chunk_text', and 'chunk_type'.
    Parameters:
        paper_id (int): The ID of the paper for which to get chunks.
        chunk_type (str): The type of chunks to retrieve. Defaults to "fulltext".
    Returns:
        list[dict]: A list of chunk records as dictionaries.
    """
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
# DETAIL (paper + chunks)
# ══════════════════════════════════════════════════════════════════

async def pg_get_detail(pdf_name: str) -> Optional[dict]:
    """Returns the paper record with the given pdf_name along with its associated chunks. The returned dictionary includes all fields from the papers table, with created_at and updated_at converted to strings for JSON serialization, and an additional 'chunks' key which is a list of chunk records as dictionaries.
    Parameters:
        pdf_name (str): The name of the PDF file for which to get detail.
    Returns:
        Optional[dict]: A dictionary containing the paper record and its associated chunks, or None if no paper with that name is found.
    """
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
    """Returns statistics about the papers and chunks in the database, including the total number of unique PDFs and the count of chunks by type. This can be used for monitoring and debugging purposes.
    Returns:
        dict: A dictionary containing the statistics.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        paper_count = await conn.fetchval("SELECT COUNT(*) FROM papers")
        chunk_rows  = await conn.fetch(
            """
            SELECT chunk_type, COUNT(*) AS cnt
            FROM   chunks
            GROUP  BY chunk_type
            """
        )
    return {
        "unique_pdf_count": int(paper_count),
        "chunks_by_type":   {r["chunk_type"]: int(r["cnt"]) for r in chunk_rows},
    }

# ══════════════════════════════════════════════════════════════════
# TRUNCATE (for reset)
# ══════════════════════════════════════════════════════════════════

async def pg_truncate_all() -> None:
    """Truncates all data from papers and chunks tables. This is a destructive operation and should be used with caution, as it will permanently delete all records in these tables.
    Returns:
        None
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Bağımlı tablolar önce, ana tablo en son
        await conn.execute(
            """
            TRUNCATE
                chunks,
                keywords,
                suggestions,
                searches
            RESTART IDENTITY CASCADE
            """
        )
        await conn.execute(
            "TRUNCATE papers RESTART IDENTITY CASCADE"
        )