"""Add company_id/branch_id to users for tenant scoping

Revision ID: add_user_company_branch_scope
Revises: add_company_admin_assignments
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_user_company_branch_scope"
down_revision = "add_company_admin_assignments"
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
    if not _column_exists("users", "company_id"):
        op.add_column("users", sa.Column("company_id", sa.Integer(), nullable=True))
    if not _column_exists("users", "branch_id"):
        op.add_column("users", sa.Column("branch_id", sa.Integer(), nullable=True))

    if not _fk_exists("users", "fk_users_company_id_companies"):
        op.create_foreign_key(
            "fk_users_company_id_companies",
            "users",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )
    if not _fk_exists("users", "fk_users_branch_id_company_branches"):
        op.create_foreign_key(
            "fk_users_branch_id_company_branches",
            "users",
            "company_branches",
            ["branch_id"],
            ["branch_id"],
            ondelete="SET NULL",
        )

    if not _index_exists("users", "ix_users_company_id"):
        op.create_index("ix_users_company_id", "users", ["company_id"], unique=False)
    if not _index_exists("users", "ix_users_branch_id"):
        op.create_index("ix_users_branch_id", "users", ["branch_id"], unique=False)


def downgrade() -> None:
    if _index_exists("users", "ix_users_branch_id"):
        op.drop_index("ix_users_branch_id", table_name="users")
    if _index_exists("users", "ix_users_company_id"):
        op.drop_index("ix_users_company_id", table_name="users")

    if _fk_exists("users", "fk_users_branch_id_company_branches"):
        op.drop_constraint("fk_users_branch_id_company_branches", "users", type_="foreignkey")
    if _fk_exists("users", "fk_users_company_id_companies"):
        op.drop_constraint("fk_users_company_id_companies", "users", type_="foreignkey")

    if _column_exists("users", "branch_id"):
        op.drop_column("users", "branch_id")
    if _column_exists("users", "company_id"):
        op.drop_column("users", "company_id")
