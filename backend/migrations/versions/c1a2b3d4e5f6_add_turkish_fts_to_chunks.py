"""add turkish fts to chunks

Mevcut `tsv` kolonu 'simple' text search config kullanıyor (bkz. 967577986706)
— bilinçli bir seçim, ama Türkçe kelimelerdeki ek farklarını (öğrenme /
öğrenmeyi) yakalayamıyor. Bunu tek başına 'turkish' config'e çevirmek yerine
(İngilizce terimlerde Türkçe stemmer'ın yanlış kök bulma riski taşıması
nedeniyle) ikinci bir kolon ekleniyor: `tsv_turkish`. Anahtar kelime arama
artık ikisini de sorgulayıp en iyi skoru kullanıyor — 'simple' ham kelime
eşleşmesini (İngilizce terimler için güvenli), 'turkish' de Türkçe ek/kök
varyasyonlarını yakalıyor.

Revision ID: c1a2b3d4e5f6
Revises: 967577986706
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, None] = '967577986706'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE chunks
        ADD COLUMN IF NOT EXISTS tsv_turkish tsvector
        GENERATED ALWAYS AS (to_tsvector('turkish', chunk_text)) STORED
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_tsv_turkish ON chunks USING GIN (tsv_turkish)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_tsv_turkish")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS tsv_turkish")
