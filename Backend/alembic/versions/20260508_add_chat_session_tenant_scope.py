"""Add company_id/branch_id to chat_sessions for tenant scoping

Revision ID: add_chat_session_tenant_scope
Revises: add_meeting_notifications
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_chat_session_tenant_scope"
down_revision = "add_meeting_notifications"
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def _column_exists(table: str, column: str) -> bool:
    if table not in _inspector().get_table_names():
        return False
    return column in {col["name"] for col in _inspector().get_columns(table)}


def _index_exists(table: str, index_name: str) -> bool:
    if table not in _inspector().get_table_names():
        return False
    return index_name in {idx["name"] for idx in _inspector().get_indexes(table)}


def _fk_exists(table: str, fk_name: str) -> bool:
    if table not in _inspector().get_table_names():
        return False
    return fk_name in {fk["name"] for fk in _inspector().get_foreign_keys(table)}


def upgrade() -> None:
    if not _column_exists("chat_sessions", "company_id"):
        op.add_column("chat_sessions", sa.Column("company_id", sa.Integer(), nullable=True))
    if not _column_exists("chat_sessions", "branch_id"):
        op.add_column("chat_sessions", sa.Column("branch_id", sa.Integer(), nullable=True))

    if not _fk_exists("chat_sessions", "fk_chat_sessions_company_id_companies"):
        op.create_foreign_key(
            "fk_chat_sessions_company_id_companies",
            "chat_sessions",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )
    if not _fk_exists("chat_sessions", "fk_chat_sessions_branch_id_company_branches"):
        op.create_foreign_key(
            "fk_chat_sessions_branch_id_company_branches",
            "chat_sessions",
            "company_branches",
            ["branch_id"],
            ["branch_id"],
            ondelete="SET NULL",
        )

    if not _index_exists("chat_sessions", "ix_chat_sessions_company_id"):
        op.create_index("ix_chat_sessions_company_id", "chat_sessions", ["company_id"], unique=False)
    if not _index_exists("chat_sessions", "ix_chat_sessions_branch_id"):
        op.create_index("ix_chat_sessions_branch_id", "chat_sessions", ["branch_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE chat_sessions cs
            JOIN (
                SELECT
                    cm.chat_id AS chat_id,
                    MIN(u.company_id) AS company_id,
                    MIN(u.branch_id) AS branch_id
                FROM chat_members cm
                JOIN users u ON u.user_id = cm.user_id
                WHERE u.company_id IS NOT NULL
                GROUP BY cm.chat_id
            ) t ON t.chat_id = cs.chat_id
            SET
                cs.company_id = COALESCE(cs.company_id, t.company_id),
                cs.branch_id = COALESCE(cs.branch_id, t.branch_id)
            WHERE cs.company_id IS NULL
            """
        )
    )


def downgrade() -> None:
    if _index_exists("chat_sessions", "ix_chat_sessions_branch_id"):
        op.drop_index("ix_chat_sessions_branch_id", table_name="chat_sessions")
    if _index_exists("chat_sessions", "ix_chat_sessions_company_id"):
        op.drop_index("ix_chat_sessions_company_id", table_name="chat_sessions")

    if _fk_exists("chat_sessions", "fk_chat_sessions_branch_id_company_branches"):
        op.drop_constraint("fk_chat_sessions_branch_id_company_branches", "chat_sessions", type_="foreignkey")
    if _fk_exists("chat_sessions", "fk_chat_sessions_company_id_companies"):
        op.drop_constraint("fk_chat_sessions_company_id_companies", "chat_sessions", type_="foreignkey")

    if _column_exists("chat_sessions", "branch_id"):
        op.drop_column("chat_sessions", "branch_id")
    if _column_exists("chat_sessions", "company_id"):
        op.drop_column("chat_sessions", "company_id")
