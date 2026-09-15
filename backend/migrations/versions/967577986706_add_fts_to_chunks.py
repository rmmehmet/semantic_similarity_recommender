"""add fts to chunks

Hybrid search'ün anahtar kelime (lexical) tarafı — Milvus sunucu sürümü
(v2.3.5) native BM25/full-text search desteklemediğinden, bu iş Postgres'in
kendi full-text search'üne (tsvector + GIN) yaptırılıyor. 'simple' text
search config kasıtlı seçildi — Türkçe/İngilizce karışık akademik metinde
dil-özel kök bulma (stemming) yanlış eşleşme riski taşır, 'simple' sadece
tokenize eder, iki dilde de tutarlı çalışır.

Revision ID: 967577986706
Revises: ab6df230fc79
Create Date: 2026-09-15 17:19:21.173392

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '967577986706'
down_revision: Union[str, None] = 'ab6df230fc79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE chunks
        ADD COLUMN IF NOT EXISTS tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', chunk_text)) STORED
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON chunks USING GIN (tsv)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_tsv")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS tsv")
