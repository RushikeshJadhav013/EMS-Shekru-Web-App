"""Add company_id to vacancies and candidates for tenant scoping

Revision ID: add_hiring_company_scope
Revises: add_calendar_company_scope
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_hiring_company_scope"
down_revision = "add_calendar_company_scope"
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
    if not _column_exists("vacancies", "company_id"):
        op.add_column("vacancies", sa.Column("company_id", sa.Integer(), nullable=True))

    if not _fk_exists("vacancies", "fk_vacancies_company_id_companies"):
        op.create_foreign_key(
            "fk_vacancies_company_id_companies",
            "vacancies",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )

    if not _index_exists("vacancies", "ix_vacancies_company_id"):
        op.create_index("ix_vacancies_company_id", "vacancies", ["company_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE vacancies v
            JOIN users u ON u.user_id = v.created_by
            SET v.company_id = u.company_id
            WHERE v.company_id IS NULL
              AND u.company_id IS NOT NULL
            """
        )
    )

    op.execute(sa.text("DELETE FROM vacancies WHERE company_id IS NULL"))

    op.alter_column("vacancies", "company_id", existing_type=sa.Integer(), nullable=False)

    if not _column_exists("candidates", "company_id"):
        op.add_column("candidates", sa.Column("company_id", sa.Integer(), nullable=True))

    if not _fk_exists("candidates", "fk_candidates_company_id_companies"):
        op.create_foreign_key(
            "fk_candidates_company_id_companies",
            "candidates",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )

    if not _index_exists("candidates", "ix_candidates_company_id"):
        op.create_index("ix_candidates_company_id", "candidates", ["company_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE candidates c
            JOIN vacancies v ON v.vacancy_id = c.vacancy_id
            SET c.company_id = v.company_id
            WHERE c.company_id IS NULL
              AND v.company_id IS NOT NULL
            """
        )
    )

    op.execute(sa.text("DELETE FROM candidates WHERE company_id IS NULL"))

    op.alter_column("candidates", "company_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    if _column_exists("candidates", "company_id"):
        op.alter_column("candidates", "company_id", existing_type=sa.Integer(), nullable=True)

    if _index_exists("candidates", "ix_candidates_company_id"):
        op.drop_index("ix_candidates_company_id", table_name="candidates")

    if _fk_exists("candidates", "fk_candidates_company_id_companies"):
        op.drop_constraint("fk_candidates_company_id_companies", "candidates", type_="foreignkey")

    if _column_exists("candidates", "company_id"):
        op.drop_column("candidates", "company_id")

    if _column_exists("vacancies", "company_id"):
        op.alter_column("vacancies", "company_id", existing_type=sa.Integer(), nullable=True)

    if _index_exists("vacancies", "ix_vacancies_company_id"):
        op.drop_index("ix_vacancies_company_id", table_name="vacancies")

    if _fk_exists("vacancies", "fk_vacancies_company_id_companies"):
        op.drop_constraint("fk_vacancies_company_id_companies", "vacancies", type_="foreignkey")

    if _column_exists("vacancies", "company_id"):
        op.drop_column("vacancies", "company_id")
