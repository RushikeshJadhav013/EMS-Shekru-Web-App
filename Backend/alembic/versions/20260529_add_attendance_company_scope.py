"""Add company_id to attendances for tenant scoping

Revision ID: add_attendance_company_scope
Revises: add_task_company_scope
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_attendance_company_scope"
down_revision = "add_task_company_scope"
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
    if not _column_exists("attendances", "company_id"):
        op.add_column("attendances", sa.Column("company_id", sa.Integer(), nullable=True))

    if not _fk_exists("attendances", "fk_attendances_company_id_companies"):
        op.create_foreign_key(
            "fk_attendances_company_id_companies",
            "attendances",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )

    if not _index_exists("attendances", "ix_attendances_company_id"):
        op.create_index("ix_attendances_company_id", "attendances", ["company_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE attendances a
            JOIN users u ON u.user_id = a.user_id
            SET a.company_id = u.company_id
            WHERE a.company_id IS NULL
              AND u.company_id IS NOT NULL
            """
        )
    )

    op.execute(sa.text("DELETE FROM attendances WHERE company_id IS NULL"))

    op.alter_column("attendances", "company_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    if _column_exists("attendances", "company_id"):
        op.alter_column("attendances", "company_id", existing_type=sa.Integer(), nullable=True)

    if _index_exists("attendances", "ix_attendances_company_id"):
        op.drop_index("ix_attendances_company_id", table_name="attendances")

    if _fk_exists("attendances", "fk_attendances_company_id_companies"):
        op.drop_constraint("fk_attendances_company_id_companies", "attendances", type_="foreignkey")

    if _column_exists("attendances", "company_id"):
        op.drop_column("attendances", "company_id")
