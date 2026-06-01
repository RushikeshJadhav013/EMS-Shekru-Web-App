"""Add company_id to shifts for tenant scoping

Revision ID: add_shift_company_scope
Revises: add_hiring_company_scope
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_shift_company_scope"
down_revision = "add_hiring_company_scope"
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
    if not _column_exists("shifts", "company_id"):
        op.add_column("shifts", sa.Column("company_id", sa.Integer(), nullable=True))

    if not _fk_exists("shifts", "fk_shifts_company_id_companies"):
        op.create_foreign_key(
            "fk_shifts_company_id_companies",
            "shifts",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )

    if not _index_exists("shifts", "ix_shifts_company_id"):
        op.create_index("ix_shifts_company_id", "shifts", ["company_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE shifts s
            JOIN (
                SELECT sa.shift_id, MIN(u.company_id) AS company_id
                FROM shift_assignments sa
                JOIN users u ON u.user_id = sa.user_id
                WHERE u.company_id IS NOT NULL
                GROUP BY sa.shift_id
            ) mapped ON mapped.shift_id = s.shift_id
            SET s.company_id = mapped.company_id
            WHERE s.company_id IS NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE shifts s
            JOIN (
                SELECT s2.shift_id, MIN(u.company_id) AS company_id
                FROM shifts s2
                JOIN users u ON u.company_id IS NOT NULL
                    AND u.department IS NOT NULL
                    AND s2.department IS NOT NULL
                    AND (
                        LOWER(u.department) = LOWER(s2.department)
                        OR LOWER(u.department) LIKE CONCAT('%,', LOWER(s2.department))
                        OR LOWER(u.department) LIKE CONCAT(LOWER(s2.department), ',%')
                        OR LOWER(u.department) LIKE CONCAT('%,', LOWER(s2.department), ',%')
                    )
                WHERE s2.company_id IS NULL
                GROUP BY s2.shift_id
                HAVING COUNT(DISTINCT u.company_id) = 1
            ) mapped ON mapped.shift_id = s.shift_id
            SET s.company_id = mapped.company_id
            WHERE s.company_id IS NULL
            """
        )
    )

    op.execute(sa.text("DELETE FROM shifts WHERE company_id IS NULL"))

    op.alter_column("shifts", "company_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    if _column_exists("shifts", "company_id"):
        op.alter_column("shifts", "company_id", existing_type=sa.Integer(), nullable=True)

    if _index_exists("shifts", "ix_shifts_company_id"):
        op.drop_index("ix_shifts_company_id", table_name="shifts")

    if _fk_exists("shifts", "fk_shifts_company_id_companies"):
        op.drop_constraint("fk_shifts_company_id_companies", "shifts", type_="foreignkey")

    if _column_exists("shifts", "company_id"):
        op.drop_column("shifts", "company_id")
