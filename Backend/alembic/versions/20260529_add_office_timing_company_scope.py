"""Add company_id to office_timings for tenant scoping

Revision ID: add_office_timing_company_scope
Revises: user_joining_date_nullable
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_office_timing_company_scope"
down_revision = "user_joining_date_nullable"
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
    if not _column_exists("office_timings", "company_id"):
        op.add_column("office_timings", sa.Column("company_id", sa.Integer(), nullable=True))

    if not _fk_exists("office_timings", "fk_office_timings_company_id_companies"):
        op.create_foreign_key(
            "fk_office_timings_company_id_companies",
            "office_timings",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )

    if not _index_exists("office_timings", "ix_office_timings_company_id"):
        op.create_index("ix_office_timings_company_id", "office_timings", ["company_id"], unique=False)

    # Copy legacy global timings to every active company.
    op.execute(
        sa.text(
            """
            INSERT INTO office_timings (
                company_id,
                department,
                start_time,
                end_time,
                check_in_grace_minutes,
                check_out_grace_minutes,
                is_active,
                created_at,
                updated_at
            )
            SELECT
                c.company_id,
                ot.department,
                ot.start_time,
                ot.end_time,
                ot.check_in_grace_minutes,
                ot.check_out_grace_minutes,
                ot.is_active,
                ot.created_at,
                ot.updated_at
            FROM office_timings ot
            CROSS JOIN companies c
            WHERE ot.company_id IS NULL
              AND c.is_deleted = FALSE
              AND NOT EXISTS (
                  SELECT 1
                  FROM office_timings existing
                  WHERE existing.company_id = c.company_id
                    AND existing.is_active = TRUE
                    AND (
                        (existing.department IS NULL AND ot.department IS NULL)
                        OR existing.department = ot.department
                    )
              )
            """
        )
    )

    op.execute(sa.text("DELETE FROM office_timings WHERE company_id IS NULL"))

    op.alter_column("office_timings", "company_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    if _column_exists("office_timings", "company_id"):
        op.alter_column("office_timings", "company_id", existing_type=sa.Integer(), nullable=True)

    if _index_exists("office_timings", "ix_office_timings_company_id"):
        op.drop_index("ix_office_timings_company_id", table_name="office_timings")

    if _fk_exists("office_timings", "fk_office_timings_company_id_companies"):
        op.drop_constraint("fk_office_timings_company_id_companies", "office_timings", type_="foreignkey")

    if _column_exists("office_timings", "company_id"):
        op.drop_column("office_timings", "company_id")
