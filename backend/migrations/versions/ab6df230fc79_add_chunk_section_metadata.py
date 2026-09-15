"""add chunk section metadata

fulltext chunk'ları artık hangi bölüm/alt bölümden geldiğini ve hangi
sayfa(lar)ı kapsadığını taşıyor — text_preprocessing.py'deki font-boyutu/
kalınlık + numaralandırma/anahtar-kelime kalıplı başlık tespiti,
chunking_service.py tarafından her chunk'a atanıyor. title/abstract
tipi chunk'larda bu alanlar boş/NULL kalır (sayfa/bölüm kavramı yok).

Revision ID: ab6df230fc79
Revises: 3e7fcd3cc5cd
Create Date: 2026-09-15 16:53:45.301688

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'ab6df230fc79'
down_revision: Union[str, None] = '3e7fcd3cc5cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS section    TEXT DEFAULT ''")
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS subsection TEXT DEFAULT ''")
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS page_start INTEGER")
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS page_end   INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS page_end")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS page_start")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS subsection")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS section")
