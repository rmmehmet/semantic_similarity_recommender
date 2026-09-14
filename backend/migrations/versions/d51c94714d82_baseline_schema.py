"""baseline schema

Bu migration, projenin Alembic'e geçmeden önceki mevcut (canlı) veritabanı
şemasını birebir yansıtır — services/database/init_postgres.sql ile elle
kurulmuş olan tabloları, index'leri ve kısıtları versiyonlanan bir migration
altına alır. Tüm DDL IF NOT EXISTS ile yazılmıştır, bu yüzden hem sıfırdan
bir veritabanında hem de zaten bu şemaya sahip mevcut bir veritabanında
güvenle çalışır (mevcut kurulumlarda `alembic stamp head` ile de
işaretlenebilir).

Bundan sonraki tüm şema değişiklikleri (yeni users tablosu dahil) ayrı
migration'lar olarak eklenmelidir — artık init_postgres.sql elle çalıştırılmaz.

Revision ID: d51c94714d82
Revises:
Create Date: 2026-09-14 15:55:09.448216

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd51c94714d82'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id             SERIAL      PRIMARY KEY,
            pdf_name       TEXT        UNIQUE NOT NULL,
            raw_title      TEXT,
            abstract       TEXT,
            fulltext       TEXT,
            book_name      TEXT        DEFAULT '',
            year           INTEGER     DEFAULT 0,
            created_at     TIMESTAMP   DEFAULT NOW(),
            updated_at     TIMESTAMP   DEFAULT NOW(),
            milvus_synced  BOOLEAN     DEFAULT FALSE,
            content_hash   CHAR(64)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id          SERIAL      PRIMARY KEY,
            paper_id    INTEGER     REFERENCES papers(id) ON DELETE CASCADE,
            chunk_text  TEXT        NOT NULL,
            chunk_idx   INTEGER     NOT NULL,
            chunk_type  TEXT        DEFAULT 'fulltext'
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id        SERIAL      PRIMARY KEY,
            paper_id  INTEGER     REFERENCES papers(id) ON DELETE CASCADE,
            keyword   TEXT        NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id           SERIAL      PRIMARY KEY,
            query_text   TEXT        NOT NULL,
            searched_at  TIMESTAMP   DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS suggestions (
            id                       SERIAL      PRIMARY KEY,
            paper_id                 INTEGER     REFERENCES papers(id) ON DELETE SET NULL,
            similarity_analysis      TEXT,
            original_aspects         TEXT,
            improvement_suggestions  TEXT,
            topic_suggestions        TEXT,
            revised_title            TEXT,
            risk_level               TEXT,
            created_at               TIMESTAMP   DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_papers_pdf_name   ON papers(pdf_name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_papers_year       ON papers(year) WHERE year > 0")
    op.execute("CREATE INDEX IF NOT EXISTS idx_papers_unsynced   ON papers(milvus_synced) WHERE milvus_synced = FALSE")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_content_hash
            ON papers(content_hash)
            WHERE content_hash IS NOT NULL
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_paper_id   ON chunks(paper_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_type       ON chunks(chunk_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_type_paper ON chunks(paper_id, chunk_type)")

    op.execute("CREATE INDEX IF NOT EXISTS idx_keywords_paper_id ON keywords(paper_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_suggestions_paper ON suggestions(paper_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS suggestions")
    op.execute("DROP TABLE IF EXISTS searches")
    op.execute("DROP TABLE IF EXISTS keywords")
    op.execute("DROP TABLE IF EXISTS chunks")
    op.execute("DROP TABLE IF EXISTS papers")
