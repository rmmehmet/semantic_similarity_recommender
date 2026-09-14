"""scope papers per user

PDF'ler artık kullanıcıya özel bir alanda tutulur — her kullanıcı sadece
kendi yüklediği belgeleri görür/yönetir, "Proje Öneri" arama motoru da
sadece o kullanıcının kendi belgelerine karşı arama yapar. Daha önce
pdf_name ve content_hash GLOBAL olarak benzersizdi; artık (user_id, pdf_name)
ve (user_id, content_hash) çiftleri benzersiz — iki farklı kullanıcı aynı
dosya adını/içeriği kullanabilir, kendi alanlarında çakışma olmaz.

NOT: Bu migration'dan önce yüklenmiş, sahibi olmayan (user_id'siz) test
kayıtları silinir — production'da gerçek veriyle çalışırken bu adımdan
önce mutlaka o kayıtların hangi kullanıcıya ait olduğu belirlenip
UPDATE ile atanmalı, körlemesine silinmemelidir.

Revision ID: 378a33e7b67e
Revises: 23b1cc306ba5
Create Date: 2026-09-14 16:51:57.201065

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '378a33e7b67e'
down_revision: Union[str, None] = '23b1cc306ba5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sahibi olmayan eski test kayıtlarını temizle (chunks CASCADE ile gider).
    op.execute("DELETE FROM papers")

    op.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE papers ALTER COLUMN user_id SET NOT NULL")

    # Eski global benzersizlik kısıtlarını kaldır.
    op.execute("ALTER TABLE papers DROP CONSTRAINT IF EXISTS papers_pdf_name_key")
    op.execute("DROP INDEX IF EXISTS idx_papers_pdf_name")
    op.execute("DROP INDEX IF EXISTS idx_papers_content_hash")

    # Kullanıcı bazlı benzersizlik: aynı isim/içerik farklı kullanıcılarda çakışmaz.
    op.execute("CREATE UNIQUE INDEX idx_papers_user_pdfname ON papers(user_id, pdf_name)")
    op.execute("""
        CREATE UNIQUE INDEX idx_papers_user_hash
            ON papers(user_id, content_hash)
            WHERE content_hash IS NOT NULL
    """)
    op.execute("CREATE INDEX idx_papers_user_id ON papers(user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_papers_user_id")
    op.execute("DROP INDEX IF EXISTS idx_papers_user_hash")
    op.execute("DROP INDEX IF EXISTS idx_papers_user_pdfname")
    op.execute("ALTER TABLE papers DROP COLUMN IF EXISTS user_id")
    op.execute("CREATE UNIQUE INDEX papers_pdf_name_key ON papers(pdf_name)")
    op.execute("CREATE INDEX idx_papers_pdf_name ON papers(pdf_name)")
    op.execute("""
        CREATE UNIQUE INDEX idx_papers_content_hash
            ON papers(content_hash)
            WHERE content_hash IS NOT NULL
    """)
