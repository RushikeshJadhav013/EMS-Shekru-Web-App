"""Add company_id/branch_id to meetings for tenant scoping

Revision ID: add_meetings_tenant_scope
Revises: add_project_tenant_scope
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_meetings_tenant_scope"
down_revision = "add_project_tenant_scope"
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
    if not _column_exists("meetings", "company_id"):
        op.add_column("meetings", sa.Column("company_id", sa.Integer(), nullable=True))
    if not _column_exists("meetings", "branch_id"):
        op.add_column("meetings", sa.Column("branch_id", sa.Integer(), nullable=True))

    if not _fk_exists("meetings", "fk_meetings_company_id_companies"):
        op.create_foreign_key(
            "fk_meetings_company_id_companies",
            "meetings",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )
    if not _fk_exists("meetings", "fk_meetings_branch_id_company_branches"):
        op.create_foreign_key(
            "fk_meetings_branch_id_company_branches",
            "meetings",
            "company_branches",
            ["branch_id"],
            ["branch_id"],
            ondelete="SET NULL",
        )

    if not _index_exists("meetings", "ix_meetings_company_id"):
        op.create_index("ix_meetings_company_id", "meetings", ["company_id"], unique=False)
    if not _index_exists("meetings", "ix_meetings_branch_id"):
        op.create_index("ix_meetings_branch_id", "meetings", ["branch_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE meetings m
            JOIN projects p ON p.project_id = m.project_id
            SET
                m.company_id = COALESCE(m.company_id, p.company_id),
                m.branch_id = COALESCE(m.branch_id, p.branch_id)
            WHERE m.project_id IS NOT NULL
              AND m.company_id IS NULL
              AND p.company_id IS NOT NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE meetings m
            JOIN users u ON u.user_id = m.created_by_id
            SET
                m.company_id = COALESCE(m.company_id, u.company_id),
                m.branch_id = COALESCE(m.branch_id, u.branch_id)
            WHERE m.project_id IS NULL
              AND m.company_id IS NULL
              AND u.company_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    if _index_exists("meetings", "ix_meetings_branch_id"):
        op.drop_index("ix_meetings_branch_id", table_name="meetings")
    if _index_exists("meetings", "ix_meetings_company_id"):
        op.drop_index("ix_meetings_company_id", table_name="meetings")

    if _fk_exists("meetings", "fk_meetings_branch_id_company_branches"):
        op.drop_constraint("fk_meetings_branch_id_company_branches", "meetings", type_="foreignkey")
    if _fk_exists("meetings", "fk_meetings_company_id_companies"):
        op.drop_constraint("fk_meetings_company_id_companies", "meetings", type_="foreignkey")

    if _column_exists("meetings", "branch_id"):
        op.drop_column("meetings", "branch_id")
    if _column_exists("meetings", "company_id"):
        op.drop_column("meetings", "company_id")
