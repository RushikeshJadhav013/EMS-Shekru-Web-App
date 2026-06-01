"""Add company_id to company_holidays and dept_week_off_rules

Revision ID: add_calendar_company_scope
Revises: add_leave_allocation_company_scope
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_calendar_company_scope"
down_revision = "add_leave_allocation_company_scope"
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


def _backfill_holidays() -> None:
    if not _column_exists("company_holidays", "company_id"):
        return

    op.execute(
        sa.text(
            """
            UPDATE company_holidays h
            JOIN users u ON u.user_id = h.created_by
            SET h.company_id = u.company_id
            WHERE h.company_id IS NULL
              AND u.company_id IS NOT NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO company_holidays (
                company_id,
                date,
                name,
                description,
                created_by,
                is_recurring,
                created_at,
                updated_at
            )
            SELECT
                c.company_id,
                h.date,
                h.name,
                h.description,
                h.created_by,
                h.is_recurring,
                h.created_at,
                h.updated_at
            FROM companies c
            CROSS JOIN company_holidays h
            WHERE h.company_id IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM company_holidays existing
                  WHERE existing.company_id = c.company_id
                    AND existing.date = h.date
                    AND existing.name = h.name
              )
            """
        )
    )

    op.execute(sa.text("DELETE FROM company_holidays WHERE company_id IS NULL"))


def _backfill_weekoffs() -> None:
    if not _column_exists("dept_week_off_rules", "company_id"):
        return

    op.execute(
        sa.text(
            """
            UPDATE dept_week_off_rules r
            JOIN users u ON u.user_id = r.created_by
            SET r.company_id = u.company_id
            WHERE r.company_id IS NULL
              AND u.company_id IS NOT NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO dept_week_off_rules (
                company_id,
                department,
                days,
                created_by,
                is_active,
                created_at,
                updated_at
            )
            SELECT
                c.company_id,
                r.department,
                r.days,
                r.created_by,
                r.is_active,
                r.created_at,
                r.updated_at
            FROM companies c
            CROSS JOIN dept_week_off_rules r
            WHERE r.company_id IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM dept_week_off_rules existing
                  WHERE existing.company_id = c.company_id
                    AND existing.department = r.department
              )
            """
        )
    )

    op.execute(sa.text("DELETE FROM dept_week_off_rules WHERE company_id IS NULL"))


def upgrade() -> None:
    if not _column_exists("company_holidays", "company_id"):
        op.add_column("company_holidays", sa.Column("company_id", sa.Integer(), nullable=True))

    if not _fk_exists("company_holidays", "fk_company_holidays_company_id_companies"):
        op.create_foreign_key(
            "fk_company_holidays_company_id_companies",
            "company_holidays",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )

    if not _index_exists("company_holidays", "ix_company_holidays_company_id"):
        op.create_index(
            "ix_company_holidays_company_id",
            "company_holidays",
            ["company_id"],
            unique=False,
        )

    _backfill_holidays()

    if _column_exists("company_holidays", "company_id"):
        op.alter_column("company_holidays", "company_id", existing_type=sa.Integer(), nullable=False)

    if not _column_exists("dept_week_off_rules", "company_id"):
        op.add_column("dept_week_off_rules", sa.Column("company_id", sa.Integer(), nullable=True))

    if not _fk_exists("dept_week_off_rules", "fk_dept_week_off_rules_company_id_companies"):
        op.create_foreign_key(
            "fk_dept_week_off_rules_company_id_companies",
            "dept_week_off_rules",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )

    if not _index_exists("dept_week_off_rules", "ix_dept_week_off_rules_company_id"):
        op.create_index(
            "ix_dept_week_off_rules_company_id",
            "dept_week_off_rules",
            ["company_id"],
            unique=False,
        )

    _backfill_weekoffs()

    if _column_exists("dept_week_off_rules", "company_id"):
        op.alter_column("dept_week_off_rules", "company_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    if _column_exists("dept_week_off_rules", "company_id"):
        op.alter_column("dept_week_off_rules", "company_id", existing_type=sa.Integer(), nullable=True)

    if _index_exists("dept_week_off_rules", "ix_dept_week_off_rules_company_id"):
        op.drop_index("ix_dept_week_off_rules_company_id", table_name="dept_week_off_rules")

    if _fk_exists("dept_week_off_rules", "fk_dept_week_off_rules_company_id_companies"):
        op.drop_constraint(
            "fk_dept_week_off_rules_company_id_companies",
            "dept_week_off_rules",
            type_="foreignkey",
        )

    if _column_exists("dept_week_off_rules", "company_id"):
        op.drop_column("dept_week_off_rules", "company_id")

    if _column_exists("company_holidays", "company_id"):
        op.alter_column("company_holidays", "company_id", existing_type=sa.Integer(), nullable=True)

    if _index_exists("company_holidays", "ix_company_holidays_company_id"):
        op.drop_index("ix_company_holidays_company_id", table_name="company_holidays")

    if _fk_exists("company_holidays", "fk_company_holidays_company_id_companies"):
        op.drop_constraint(
            "fk_company_holidays_company_id_companies",
            "company_holidays",
            type_="foreignkey",
        )

    if _column_exists("company_holidays", "company_id"):
        op.drop_column("company_holidays", "company_id")
