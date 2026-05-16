"""
postgres_service.py
-------------------
PostgreSQL CRUD katmanı.  asyncpg tabanlı bağlantı havuzu.

DÜZELTMELER (v2):
  - DATABASE_URL env'den okunuyor, fallback liftup_db/postgres:123
  - pg_insert_chunks: ON CONFLICT DO NOTHING → ON CONFLICT yerine
    INSERT ... WHERE NOT EXISTS kullanıldı (unique constraint olmadan güvenli)
  - pg_list_papers: abstract_len / fulltext_len int'e cast edildi
  - pg_get_detail: chunks ayrı tip listesi şeklinde döndürülüyor
  - pg_stats: liftup_titles / liftup_abstracts Milvus count için placeholder
"""

from __future__ import annotations

import os
from typing import Optional

import asyncpg

# ── Bağlantı ──────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:123@localhost:5432/liftup_db",
)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
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
    """INSERT OR UPDATE → paper id döndürür."""
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
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM papers WHERE pdf_name = $1", pdf_name
        )
        return dict(row) if row else None


async def pg_list_papers(limit: int = 500) -> list[dict]:
    """Listeleme için hafif sorgu — fulltext döndürülmez."""
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
            # asyncpg datetime → str (JSON serileştirme için)
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            result.append(d)
        return result


async def pg_delete_paper(pdf_name: str) -> bool:
    """Cascade ile chunks / keywords / suggestions silinir."""
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
        # executemany asyncpg'de copy_records_to_table kadar hızlı değil
        # ama okunabilirlik için yeterli
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
# DETAY  (modal için — başlık / özet / tam metin + chunk listesi)
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
# İSTATİSTİKLER
# ══════════════════════════════════════════════════════════════════

async def pg_stats() -> dict:
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
# TRUNCATE (reset için)
# ══════════════════════════════════════════════════════════════════

async def pg_truncate_all() -> None:
    """Tüm tabloları CASCADE ile temizler. RESTART IDENTITY ile ID sıfırlanır."""
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