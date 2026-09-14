"""add users table

E-posta+şifre ile kayıt/giriş yapan kullanıcı sistemi için tablo.
Roller: 'admin' (kurucu hesap, ADMIN_EMAILS env değişkeniyle atanır) ve
'user' (herkes). E-posta ve telefon numarası benzersizdir; format
doğrulaması ve "zaten kayıtlı mı" kontrolü uygulama katmanında
(services/auth_service.py) yapılır.

Revision ID: 23b1cc306ba5
Revises: d51c94714d82
Create Date: 2026-09-14 15:57:49.202722

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '23b1cc306ba5'
down_revision: Union[str, None] = 'd51c94714d82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id             SERIAL      PRIMARY KEY,
            email          TEXT        NOT NULL,
            phone          TEXT        NOT NULL,
            first_name     TEXT        NOT NULL,
            last_name      TEXT        NOT NULL,
            password_hash  TEXT        NOT NULL,
            role           TEXT        NOT NULL DEFAULT 'user'
                                       CHECK (role IN ('user', 'admin')),
            is_active      BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at     TIMESTAMP   DEFAULT NOW(),
            updated_at     TIMESTAMP   DEFAULT NOW()
        )
    """)

    # E-posta/telefon karşılaştırmaları case-insensitive normalize edilerek
    # (lower(email)) uygulama katmanında saklanır; unique index de buna göre.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users (email)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users (phone)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users")
