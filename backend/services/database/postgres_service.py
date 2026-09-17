from __future__ import annotations

import json
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
    user_id: int,
    book_name: str = "",
    year: int = 0,
    content_hash: Optional[str] = None,
) -> int:
    """
    INSERT OR UPDATE — milvus_synced FALSE olarak başlar.
    Milvus yazımı tamamlandıktan sonra pg_mark_synced() çağrılmalıdır.
    Belgeler kullanıcıya özeldir: benzersizlik (user_id, pdf_name) çiftine göredir.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO papers
                (pdf_name, raw_title, abstract, fulltext, book_name, year, content_hash, user_id, milvus_synced)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE)
            ON CONFLICT (user_id, pdf_name) DO UPDATE
                SET raw_title     = EXCLUDED.raw_title,
                    abstract      = EXCLUDED.abstract,
                    fulltext      = EXCLUDED.fulltext,
                    book_name     = EXCLUDED.book_name,
                    year          = EXCLUDED.year,
                    content_hash  = EXCLUDED.content_hash,
                    milvus_synced = FALSE,
                    updated_at    = NOW()
            RETURNING id
            """,
            pdf_name, raw_title, abstract, fulltext, book_name, year, content_hash, user_id,
        )
        return int(row["id"])


async def pg_get_paper_by_hash(content_hash: str, user_id: int) -> Optional[dict]:
    """
    Bu kullanıcının belgeleri içinde içerik hash'i ile eşleşen kaydı döner
    (dosya adından bağımsız). Aynı belgenin farklı bir isimle yeniden
    yüklenmesini tespit etmek için kullanılır — kullanıcının KENDİ alanıyla sınırlıdır.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM papers WHERE content_hash = $1 AND user_id = $2",
            content_hash, user_id,
        )
        return dict(row) if row else None


async def pg_mark_synced(pdf_name: str, user_id: int) -> None:
    """
    Milvus yazımı başarıyla tamamlandığında çağrılır.
    milvus_synced = TRUE yapar.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE papers SET milvus_synced = TRUE, updated_at = NOW() WHERE pdf_name = $1 AND user_id = $2",
            pdf_name, user_id,
        )
    logger.info("[PG] milvus_synced=TRUE — %s (user=%s)", pdf_name, user_id)


async def pg_get_unsynced() -> list[dict]:
    """
    milvus_synced=FALSE olan tüm kayıtları (TÜM kullanıcılar dahil) döner.
    Reconcile işlemi (admin-only, global bakım) bu listeyi kullanır.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, pdf_name, raw_title, book_name, year, user_id, created_at
            FROM   papers
            WHERE  milvus_synced = FALSE
            ORDER  BY created_at DESC
            """
        )
        return [dict(r) for r in rows]


async def pg_get_paper(pdf_name: str, user_id: int) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM papers WHERE pdf_name = $1 AND user_id = $2", pdf_name, user_id
        )
        return dict(row) if row else None


async def pg_get_papers_by_names(pdf_names: list[str], user_id: int) -> dict[str, dict]:
    """
    N+1 sorununu çözer — tek sorguda birden fazla paper getirir.
    Sadece bu kullanıcının belgeleriyle sınırlıdır.
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
            WHERE  user_id = $1 AND pdf_name = ANY($2::text[])
            """,
            user_id, pdf_names,
        )
        return {r["pdf_name"]: dict(r) for r in rows}


async def pg_list_papers(limit: int, user_id: int) -> list[dict]:
    """Sadece bu kullanıcının belgelerini listeler."""
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
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id, limit,
        )
        result = []
        for r in rows:
            d = dict(r)
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            result.append(d)
        return result


async def pg_delete_paper(pdf_name: str, user_id: int) -> bool:
    """Sadece bu kullanıcıya ait kaydı siler."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM papers WHERE pdf_name = $1 AND user_id = $2", pdf_name, user_id
        )
        return result.split()[-1] != "0"


async def pg_paper_exists(pdf_name: str, user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM papers WHERE pdf_name = $1 AND user_id = $2", pdf_name, user_id
        )
        return row is not None


async def pg_get_all_pdf_names() -> set[tuple[int, str]]:
    """Reconcile için PG'deki tüm (user_id, pdf_name) çiftlerini döner."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, pdf_name FROM papers")
        return {(r["user_id"], r["pdf_name"]) for r in rows}


# ══════════════════════════════════════════════════════════════════
# CHUNKS
# ══════════════════════════════════════════════════════════════════

async def pg_insert_chunks(paper_id: int, chunks: list[dict]) -> None:
    """
    chunks: services/chunking_service.py::build_chunk_records()'ın döndürdüğü
    kayıtlar — section/subsection/page_start/page_end alanları sadece
    chunk_type='fulltext' için doludur, title/abstract'ta boş/None.
    """
    if not chunks:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO chunks (paper_id, chunk_text, chunk_idx, chunk_type, section, subsection, page_start, page_end)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            [
                (
                    paper_id, c["chunk_text"], c["chunk_idx"], c["chunk_type"],
                    c.get("section") or "", c.get("subsection") or "",
                    c.get("page_start"), c.get("page_end"),
                )
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
            SELECT chunk_idx, chunk_text, chunk_type, section, subsection, page_start, page_end
            FROM   chunks
            WHERE  paper_id = $1 AND chunk_type = $2
            ORDER  BY chunk_idx
            """,
            paper_id, chunk_type,
        )
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# FULL-TEXT (KEYWORD) SEARCH — hibrit aramanın lexical tarafı
# ══════════════════════════════════════════════════════════════════

async def pg_keyword_search_chunks(
    user_id: int,
    query_text: str,
    pdf_names: Optional[list[str]] = None,
    limit: int = 40,
) -> list[dict]:
    """
    Postgres full-text search (tsvector/ts_rank) — Milvus'un vektör aramasının
    kaçırabileceği tam kelime/kısaltma/özel isim eşleşmelerini bulur. Sadece
    bu kullanıcının fulltext chunk'ları içinde arar; pdf_names verilirse ona
    da sınırlanır. bkz. services/hybrid_search.py::fuse_hits.

    İki tsvector kolonu birden sorgulanır: `tsv` ('simple' config — ham kelime
    eşleşmesi, İngilizce terimlerde güvenli) ve `tsv_turkish` ('turkish'
    config — Türkçe ek/kök varyasyonlarını yakalar, örn. öğrenme/öğrenmeyi).
    İkisi tek bir stemmer'a zorlanmıyor çünkü akademik metin Türkçe/İngilizce
    karışık; Türkçe stemmer İngilizce kelimelere uygulanırsa yanlış kök
    bulma riski taşır (bkz. migration c1a2b3d4e5f6). Bir chunk her iki
    config'te de eşleşirse en yüksek rank kullanılır (GREATEST).

    Döner: [{pdf_name, chunk_idx, text, section, subsection, page_start,
             page_end, keyword_rank}, ...] — keyword_rank'e göre azalan sıralı.
    "text" alanı Milvus hit'leriyle aynı adı taşır (fuse_hits ile doğrudan
    birleştirilebilsin diye); "score" DEĞİL "keyword_rank" adı kasıtlıdır —
    bkz. hybrid_search.py'deki not (cosine skoruyla karıştırılmamalı).
    """
    query_text = (query_text or "").strip()
    if not query_text:
        return []

    pool = await get_pool()
    async with pool.acquire() as conn:
        if pdf_names:
            rows = await conn.fetch(
                """
                SELECT p.pdf_name, c.chunk_idx, c.chunk_text AS text,
                       c.section, c.subsection, c.page_start, c.page_end,
                       GREATEST(
                           ts_rank(c.tsv,         plainto_tsquery('simple',  $2)),
                           ts_rank(c.tsv_turkish, plainto_tsquery('turkish', $2))
                       ) AS keyword_rank
                FROM   chunks c
                JOIN   papers p ON p.id = c.paper_id
                WHERE  p.user_id = $1 AND c.chunk_type = 'fulltext'
                       AND p.pdf_name = ANY($3::text[])
                       AND (c.tsv @@ plainto_tsquery('simple', $2)
                            OR c.tsv_turkish @@ plainto_tsquery('turkish', $2))
                ORDER  BY keyword_rank DESC
                LIMIT  $4
                """,
                user_id, query_text, pdf_names, limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT p.pdf_name, c.chunk_idx, c.chunk_text AS text,
                       c.section, c.subsection, c.page_start, c.page_end,
                       GREATEST(
                           ts_rank(c.tsv,         plainto_tsquery('simple',  $2)),
                           ts_rank(c.tsv_turkish, plainto_tsquery('turkish', $2))
                       ) AS keyword_rank
                FROM   chunks c
                JOIN   papers p ON p.id = c.paper_id
                WHERE  p.user_id = $1 AND c.chunk_type = 'fulltext'
                       AND (c.tsv @@ plainto_tsquery('simple', $2)
                            OR c.tsv_turkish @@ plainto_tsquery('turkish', $2))
                ORDER  BY keyword_rank DESC
                LIMIT  $3
                """,
                user_id, query_text, limit,
            )
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# DETAIL
# ══════════════════════════════════════════════════════════════════

async def pg_get_detail(pdf_name: str, user_id: int) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM papers WHERE pdf_name = $1 AND user_id = $2", pdf_name, user_id
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
            SELECT chunk_idx, chunk_text, chunk_type, section, subsection, page_start, page_end
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

async def pg_stats(user_id: int) -> dict:
    """Sadece bu kullanıcının belgelerine ait istatistikler."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        paper_count = await conn.fetchval(
            "SELECT COUNT(*) FROM papers WHERE user_id = $1", user_id
        )
        unsynced_count = await conn.fetchval(
            "SELECT COUNT(*) FROM papers WHERE milvus_synced = FALSE AND user_id = $1", user_id
        )
        chunk_rows = await conn.fetch(
            """
            SELECT c.chunk_type, COUNT(*) AS cnt
            FROM   chunks c
            JOIN   papers p ON p.id = c.paper_id
            WHERE  p.user_id = $1
            GROUP  BY c.chunk_type
            """,
            user_id,
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
    # NOT: `users` tablosu buraya KASITLI OLARAK dahil edilmemiştir —
    # veri tabanı sıfırlama (reset) hiçbir zaman kullanıcı hesaplarını silmemeli.


# ══════════════════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════════════════

async def pg_create_user(
    email: str,
    phone: str,
    first_name: str,
    last_name: str,
    password_hash: str,
    role: str = "user",
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (email, phone, first_name, last_name, password_hash, role)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, email, phone, first_name, last_name, role, is_active, created_at
            """,
            email, phone, first_name, last_name, password_hash, role,
        )
        return dict(row)


async def pg_get_user_by_email(email: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
        return dict(row) if row else None


async def pg_get_user_by_phone(phone: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE phone = $1", phone)
        return dict(row) if row else None


async def pg_get_user_by_id(user_id: int) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════
# CHAT CONVERSATIONS
# ══════════════════════════════════════════════════════════════════

async def pg_create_conversation(user_id: int, title: str, pdf_names: list[str]) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO chat_conversations (user_id, title, pdf_names)
            VALUES ($1, $2, $3::jsonb)
            RETURNING id, title, pdf_names, created_at, updated_at
            """,
            user_id, title, json.dumps(pdf_names),
        )
        d = dict(row)
        d["pdf_names"] = json.loads(d["pdf_names"]) if isinstance(d["pdf_names"], str) else d["pdf_names"]
        return d


async def pg_list_conversations(user_id: int, limit: int = 200) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, updated_at
            FROM   chat_conversations
            WHERE  user_id = $1
            ORDER  BY updated_at DESC
            LIMIT  $2
            """,
            user_id, limit,
        )
        return [dict(r) for r in rows]


async def pg_get_conversation(conversation_id: int, user_id: int) -> Optional[dict]:
    """Sahiplik kontrolüyle birlikte — başka kullanıcının sohbeti None döner."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, pdf_names, created_at, updated_at
            FROM   chat_conversations
            WHERE  id = $1 AND user_id = $2
            """,
            conversation_id, user_id,
        )
        if not row:
            return None
        d = dict(row)
        d["pdf_names"] = json.loads(d["pdf_names"]) if isinstance(d["pdf_names"], str) else d["pdf_names"]
        return d


async def pg_touch_conversation(conversation_id: int, pdf_names: list[str]) -> None:
    """Mesaj her gönderildiğinde çağrılır — güncel PDF kapsamını ve updated_at'i yazar."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE chat_conversations
            SET    pdf_names = $2::jsonb, updated_at = NOW()
            WHERE  id = $1
            """,
            conversation_id, json.dumps(pdf_names),
        )


async def pg_delete_conversation(conversation_id: int, user_id: int) -> bool:
    """Sadece bu kullanıcıya ait sohbeti siler (mesajlar CASCADE ile gider)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM chat_conversations WHERE id = $1 AND user_id = $2",
            conversation_id, user_id,
        )
        return result.split()[-1] != "0"


async def pg_add_message(conversation_id: int, role: str, content: str, sources: list[dict]) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO chat_messages (conversation_id, role, content, sources)
            VALUES ($1, $2, $3, $4::jsonb)
            """,
            conversation_id, role, content, json.dumps(sources),
        )


async def pg_get_conversation_messages(conversation_id: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content, sources, created_at
            FROM   chat_messages
            WHERE  conversation_id = $1
            ORDER  BY created_at
            """,
            conversation_id,
        )
        result = []
        for r in rows:
            d = dict(r)
            d["sources"] = json.loads(d["sources"]) if isinstance(d["sources"], str) else d["sources"]
            result.append(d)
        return result


async def pg_get_recent_messages(conversation_id: int, limit: int) -> list[dict]:
    """En son N mesajı, eskiden yeniye sıralı döner (LLM bağlamı için)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content
            FROM   (
                SELECT role, content, created_at
                FROM   chat_messages
                WHERE  conversation_id = $1
                ORDER  BY created_at DESC
                LIMIT  $2
            ) recent
            ORDER BY created_at
            """,
            conversation_id, limit,
        )
        return [dict(r) for r in rows]