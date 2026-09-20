"""add token_version to users

Şifre değişince eski JWT'lerin (7 günlük ömür boyunca) geçerli kalmaya
devam etmesini önlemek için: her kullanıcının bir sayacı var, JWT bu
sayacın anlık değerini claim olarak taşır, her istekte DB'deki güncel
değerle karşılaştırılır (bkz. services/auth.py). Şifre değiştiğinde
sayaç artırılır — o ana kadar üretilmiş tüm token'lar (diğer cihazlar/
çalıntı token dahil) anında geçersiz olur.

Revision ID: f2a91c7d4e3b
Revises: c1a2b3d4e5f6
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f2a91c7d4e3b'
down_revision: Union[str, None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 1
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS token_version")
