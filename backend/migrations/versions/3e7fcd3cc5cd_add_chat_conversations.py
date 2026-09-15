"""add chat conversations

"PDF Sohbet" özelliği artık konuşmaları kalıcı hale getiriyor — daha önce
sohbet tamamen frontend React state'indeydi ve herhangi bir sayfa
yenilenmesinde/remount'ta kayboluyordu. Bu migration iki tablo ekler:
chat_conversations (kullanıcı başına sohbet listesi, her biri opsiyonel
bir PDF kapsamı taşır) ve chat_messages (her sohbetin mesajları).

Revision ID: 3e7fcd3cc5cd
Revises: 378a33e7b67e
Create Date: 2026-09-15 14:52:24.563627

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3e7fcd3cc5cd'
down_revision: Union[str, None] = '378a33e7b67e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE chat_conversations (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title       TEXT NOT NULL,
            pdf_names   JSONB NOT NULL DEFAULT '[]',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX idx_chat_conversations_user_updated
            ON chat_conversations(user_id, updated_at DESC)
    """)

    op.execute("""
        CREATE TABLE chat_messages (
            id              SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
            role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content         TEXT NOT NULL,
            sources         JSONB NOT NULL DEFAULT '[]',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX idx_chat_messages_conversation
            ON chat_messages(conversation_id, created_at)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chat_messages")
    op.execute("DROP TABLE IF EXISTS chat_conversations")
