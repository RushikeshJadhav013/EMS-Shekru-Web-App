"""Add company_id to departments for tenant scoping

Revision ID: add_department_company_scope
Revises: add_shift_company_scope
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_department_company_scope"
down_revision = "add_shift_company_scope"
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


def _drop_global_code_unique() -> None:
    insp = _inspector()
    for uc in insp.get_unique_constraints("departments"):
        if uc.get("column_names") == ["code"]:
            op.drop_constraint(uc["name"], "departments", type_="unique")
            return
    for idx in insp.get_indexes("departments"):
        if idx.get("unique") and idx.get("column_names") == ["code"]:
            op.drop_index(idx["name"], table_name="departments")
            return


def upgrade() -> None:
    if not _column_exists("departments", "company_id"):
        op.add_column("departments", sa.Column("company_id", sa.Integer(), nullable=True))

    if not _fk_exists("departments", "fk_departments_company_id_companies"):
        op.create_foreign_key(
            "fk_departments_company_id_companies",
            "departments",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )

    if not _index_exists("departments", "ix_departments_company_id"):
        op.create_index("ix_departments_company_id", "departments", ["company_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE departments d
            JOIN users u ON u.user_id = d.manager_id
            SET d.company_id = u.company_id
            WHERE d.company_id IS NULL
              AND u.company_id IS NOT NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE departments d
            JOIN (
                SELECT d2.id, MIN(u.company_id) AS company_id
                FROM departments d2
                JOIN users u ON u.company_id IS NOT NULL
                    AND u.department IS NOT NULL
                    AND (
                        LOWER(u.department) = LOWER(d2.name)
                        OR LOWER(u.department) LIKE CONCAT('%,', LOWER(d2.name))
                        OR LOWER(u.department) LIKE CONCAT(LOWER(d2.name), ',%')
                        OR LOWER(u.department) LIKE CONCAT('%,', LOWER(d2.name), ',%')
                    )
                WHERE d2.company_id IS NULL
                GROUP BY d2.id
                HAVING COUNT(DISTINCT u.company_id) = 1
            ) mapped ON mapped.id = d.id
            SET d.company_id = mapped.company_id
            WHERE d.company_id IS NULL
            """
        )
    )

    op.execute(sa.text("DELETE FROM departments WHERE company_id IS NULL"))

    op.alter_column("departments", "company_id", existing_type=sa.Integer(), nullable=False)

    _drop_global_code_unique()

    if not _index_exists("departments", "uq_departments_company_code"):
        op.create_unique_constraint(
            "uq_departments_company_code",
            "departments",
            ["company_id", "code"],
        )


def downgrade() -> None:
    if _index_exists("departments", "uq_departments_company_code"):
        op.drop_constraint("uq_departments_company_code", "departments", type_="unique")

    if _column_exists("departments", "company_id"):
        op.alter_column("departments", "company_id", existing_type=sa.Integer(), nullable=True)

    if _index_exists("departments", "ix_departments_company_id"):
        op.drop_index("ix_departments_company_id", table_name="departments")

    if _fk_exists("departments", "fk_departments_company_id_companies"):
        op.drop_constraint("fk_departments_company_id_companies", "departments", type_="foreignkey")

    if _column_exists("departments", "company_id"):
        op.drop_column("departments", "company_id")

    if not _index_exists("departments", "code"):
        op.create_index("code", "departments", ["code"], unique=True)
