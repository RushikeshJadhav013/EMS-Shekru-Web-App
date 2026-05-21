"""Add chat_sessions and chat_members tables for chat metadata

Revision ID: add_chat_metadata
Revises: add_work_summary_report
Create Date: 2025-12-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_chat_metadata"
down_revision = "add_work_summary_report"
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
    if not _table_exists("chat_sessions"):
        op.create_table(
            "chat_sessions",
            sa.Column("chat_id", sa.String(length=255), primary_key=True),
            sa.Column("chat_type", sa.String(length=20), nullable=False, index=True),
            sa.Column("name", sa.String(length=255), nullable=True),
            sa.Column(
                "created_by_id",
                sa.Integer(),
                sa.ForeignKey("users.user_id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("member_count", sa.Integer(), nullable=True),
            sa.Column("last_message_at", sa.DateTime(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )

    if not _index_exists("chat_sessions", "ix_chat_sessions_chat_id"):
        op.create_index("ix_chat_sessions_chat_id", "chat_sessions", ["chat_id"], unique=True)
    if not _index_exists("chat_sessions", "ix_chat_sessions_chat_type"):
        op.create_index("ix_chat_sessions_chat_type", "chat_sessions", ["chat_type"], unique=False)
    if not _index_exists("chat_sessions", "ix_chat_sessions_created_by_id"):
        op.create_index("ix_chat_sessions_created_by_id", "chat_sessions", ["created_by_id"], unique=False)

    if not _table_exists("chat_members"):
        op.create_table(
            "chat_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "chat_id",
                sa.String(length=255),
                sa.ForeignKey("chat_sessions.chat_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.user_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(length=50), nullable=False, server_default="member"),
            sa.Column("joined_at", sa.DateTime(), nullable=True),
        )

    if not _index_exists("chat_members", "ix_chat_members_id"):
        op.create_index("ix_chat_members_id", "chat_members", ["id"], unique=True)
    if not _index_exists("chat_members", "ix_chat_members_chat_id"):
        op.create_index("ix_chat_members_chat_id", "chat_members", ["chat_id"], unique=False)
    if not _index_exists("chat_members", "ix_chat_members_user_id"):
        op.create_index("ix_chat_members_user_id", "chat_members", ["user_id"], unique=False)
    if not _index_exists("chat_members", "ix_chat_members_chat_id_user_id"):
        op.create_index(
            "ix_chat_members_chat_id_user_id", "chat_members", ["chat_id", "user_id"], unique=True
        )


def downgrade() -> None:
    if _index_exists("chat_members", "ix_chat_members_chat_id_user_id"):
        op.drop_index("ix_chat_members_chat_id_user_id", table_name="chat_members")
    if _index_exists("chat_members", "ix_chat_members_user_id"):
        op.drop_index("ix_chat_members_user_id", table_name="chat_members")
    if _index_exists("chat_members", "ix_chat_members_chat_id"):
        op.drop_index("ix_chat_members_chat_id", table_name="chat_members")
    if _index_exists("chat_members", "ix_chat_members_id"):
        op.drop_index("ix_chat_members_id", table_name="chat_members")
    if _table_exists("chat_members"):
        op.drop_table("chat_members")

    if _index_exists("chat_sessions", "ix_chat_sessions_created_by_id"):
        op.drop_index("ix_chat_sessions_created_by_id", table_name="chat_sessions")
    if _index_exists("chat_sessions", "ix_chat_sessions_chat_type"):
        op.drop_index("ix_chat_sessions_chat_type", table_name="chat_sessions")
    if _index_exists("chat_sessions", "ix_chat_sessions_chat_id"):
        op.drop_index("ix_chat_sessions_chat_id", table_name="chat_sessions")
    if _table_exists("chat_sessions"):
        op.drop_table("chat_sessions")
