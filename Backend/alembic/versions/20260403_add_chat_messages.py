"""Add chat_messages table (MySQL-backed chat)

Revision ID: add_chat_messages
Revises: add_chat_metadata
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_chat_messages"
down_revision = "add_chat_metadata"
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return name in _inspector().get_table_names()


def _index_exists(table: str, index_name: str) -> bool:
    if not _table_exists(table):
        return False
    return index_name in {idx["name"] for idx in _inspector().get_indexes(table)}


def upgrade() -> None:
    if not _table_exists("chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("msg_id", sa.String(length=36), primary_key=True),
            sa.Column(
                "chat_id",
                sa.String(length=255),
                sa.ForeignKey("chat_sessions.chat_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "sender_id",
                sa.Integer(),
                sa.ForeignKey("users.user_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("timestamp", sa.Float(), nullable=False),
            sa.Column("read_by", sa.JSON(), nullable=False),
            sa.Column("file_url", sa.String(length=1024), nullable=True),
            sa.Column("file_name", sa.String(length=512), nullable=True),
            sa.Column("file_type", sa.String(length=255), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
        )

    if not _index_exists("chat_messages", "ix_chat_messages_chat_id"):
        op.create_index("ix_chat_messages_chat_id", "chat_messages", ["chat_id"], unique=False)
    if not _index_exists("chat_messages", "ix_chat_messages_sender_id"):
        op.create_index("ix_chat_messages_sender_id", "chat_messages", ["sender_id"], unique=False)
    if not _index_exists("chat_messages", "ix_chat_messages_chat_id_timestamp"):
        op.create_index(
            "ix_chat_messages_chat_id_timestamp",
            "chat_messages",
            ["chat_id", "timestamp"],
            unique=False,
        )


def downgrade() -> None:
    if _index_exists("chat_messages", "ix_chat_messages_chat_id_timestamp"):
        op.drop_index("ix_chat_messages_chat_id_timestamp", table_name="chat_messages")
    if _index_exists("chat_messages", "ix_chat_messages_sender_id"):
        op.drop_index("ix_chat_messages_sender_id", table_name="chat_messages")
    if _index_exists("chat_messages", "ix_chat_messages_chat_id"):
        op.drop_index("ix_chat_messages_chat_id", table_name="chat_messages")
    if _table_exists("chat_messages"):
        op.drop_table("chat_messages")
