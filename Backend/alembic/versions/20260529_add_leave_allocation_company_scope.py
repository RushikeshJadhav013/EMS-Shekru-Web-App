"""Add company_id to leave_allocation_config for per-tenant leave policy

Revision ID: add_leave_allocation_company_scope
Revises: add_leave_company_scope
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_leave_allocation_company_scope"
down_revision = "add_leave_company_scope"
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
    if not _column_exists("leave_allocation_config", "company_id"):
        op.add_column(
            "leave_allocation_config",
            sa.Column("company_id", sa.Integer(), nullable=True),
        )

    if not _fk_exists("leave_allocation_config", "fk_leave_allocation_config_company_id_companies"):
        op.create_foreign_key(
            "fk_leave_allocation_config_company_id_companies",
            "leave_allocation_config",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )

    if not _index_exists("leave_allocation_config", "ix_leave_allocation_config_company_id"):
        op.create_index(
            "ix_leave_allocation_config_company_id",
            "leave_allocation_config",
            ["company_id"],
            unique=False,
        )

    # Copy legacy global config to every company (from latest active/global row).
    op.execute(
        sa.text(
            """
            INSERT INTO leave_allocation_config (
                company_id,
                total_annual_leave,
                sick_leave_allocation,
                casual_leave_allocation,
                other_leave_allocation,
                is_active,
                created_at,
                updated_at,
                updated_by
            )
            SELECT
                c.company_id,
                lac.total_annual_leave,
                lac.sick_leave_allocation,
                lac.casual_leave_allocation,
                lac.other_leave_allocation,
                lac.is_active,
                lac.created_at,
                lac.updated_at,
                lac.updated_by
            FROM companies c
            CROSS JOIN (
                SELECT *
                FROM leave_allocation_config
                WHERE company_id IS NULL
                ORDER BY is_active DESC, id DESC
                LIMIT 1
            ) lac
            WHERE NOT EXISTS (
                SELECT 1
                FROM leave_allocation_config existing
                WHERE existing.company_id = c.company_id
            )
            """
        )
    )

    # Default policy for companies that still have no row.
    op.execute(
        sa.text(
            """
            INSERT INTO leave_allocation_config (
                company_id,
                total_annual_leave,
                sick_leave_allocation,
                casual_leave_allocation,
                other_leave_allocation,
                is_active
            )
            SELECT
                c.company_id,
                15,
                10,
                5,
                0,
                TRUE
            FROM companies c
            WHERE NOT EXISTS (
                SELECT 1
                FROM leave_allocation_config lac
                WHERE lac.company_id = c.company_id
            )
            """
        )
    )

    op.execute(sa.text("DELETE FROM leave_allocation_config WHERE company_id IS NULL"))

    op.alter_column(
        "leave_allocation_config",
        "company_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    if _column_exists("leave_allocation_config", "company_id"):
        op.alter_column(
            "leave_allocation_config",
            "company_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

    if _index_exists("leave_allocation_config", "ix_leave_allocation_config_company_id"):
        op.drop_index(
            "ix_leave_allocation_config_company_id",
            table_name="leave_allocation_config",
        )

    if _fk_exists("leave_allocation_config", "fk_leave_allocation_config_company_id_companies"):
        op.drop_constraint(
            "fk_leave_allocation_config_company_id_companies",
            "leave_allocation_config",
            type_="foreignkey",
        )

    if _column_exists("leave_allocation_config", "company_id"):
        op.drop_column("leave_allocation_config", "company_id")
