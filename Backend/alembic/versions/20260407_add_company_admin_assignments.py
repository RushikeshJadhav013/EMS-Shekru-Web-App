"""Add company_admin_assignments for direct company-level admin mapping

Revision ID: add_company_admin_assignments
Revises: alter_chat_messages_timestamp_to_datetime
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_company_admin_assignments"
down_revision = "alter_chat_messages_timestamp_to_datetime"
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
    if not _table_exists("company_admin_assignments"):
        op.create_table(
            "company_admin_assignments",
            sa.Column("assignment_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("admin_user_id", sa.Integer(), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["admin_user_id"],
                ["users.user_id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"],
                ["companies.company_id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["created_by"],
                ["super_admins.super_admin_id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["updated_by"],
                ["super_admins.super_admin_id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("assignment_id"),
            sa.UniqueConstraint("admin_user_id", "company_id", name="uq_company_admin_user"),
        )

    if not _index_exists("company_admin_assignments", "ix_company_admin_assignments_admin_user_id"):
        op.create_index(
            "ix_company_admin_assignments_admin_user_id",
            "company_admin_assignments",
            ["admin_user_id"],
            unique=False,
        )
    if not _index_exists("company_admin_assignments", "ix_company_admin_assignments_company_id"):
        op.create_index(
            "ix_company_admin_assignments_company_id",
            "company_admin_assignments",
            ["company_id"],
            unique=False,
        )


def downgrade() -> None:
    if _index_exists("company_admin_assignments", "ix_company_admin_assignments_company_id"):
        op.drop_index("ix_company_admin_assignments_company_id", table_name="company_admin_assignments")
    if _index_exists("company_admin_assignments", "ix_company_admin_assignments_admin_user_id"):
        op.drop_index("ix_company_admin_assignments_admin_user_id", table_name="company_admin_assignments")
    if _table_exists("company_admin_assignments"):
        op.drop_table("company_admin_assignments")
