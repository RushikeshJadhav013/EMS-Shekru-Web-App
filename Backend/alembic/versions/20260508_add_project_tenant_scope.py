"""Add company_id/branch_id to projects for tenant scoping

Revision ID: add_project_tenant_scope
Revises: add_chat_session_tenant_scope
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_project_tenant_scope"
down_revision = "add_chat_session_tenant_scope"
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
    if not _column_exists("projects", "company_id"):
        op.add_column("projects", sa.Column("company_id", sa.Integer(), nullable=True))
    if not _column_exists("projects", "branch_id"):
        op.add_column("projects", sa.Column("branch_id", sa.Integer(), nullable=True))

    if not _fk_exists("projects", "fk_projects_company_id_companies"):
        op.create_foreign_key(
            "fk_projects_company_id_companies",
            "projects",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )
    if not _fk_exists("projects", "fk_projects_branch_id_company_branches"):
        op.create_foreign_key(
            "fk_projects_branch_id_company_branches",
            "projects",
            "company_branches",
            ["branch_id"],
            ["branch_id"],
            ondelete="SET NULL",
        )

    if not _index_exists("projects", "ix_projects_company_id"):
        op.create_index("ix_projects_company_id", "projects", ["company_id"], unique=False)
    if not _index_exists("projects", "ix_projects_branch_id"):
        op.create_index("ix_projects_branch_id", "projects", ["branch_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE projects p
            JOIN (
                SELECT
                    pm.project_id AS project_id,
                    MIN(u.company_id) AS company_id,
                    MIN(u.branch_id) AS branch_id
                FROM project_members pm
                JOIN users u ON u.user_id = pm.user_id
                WHERE pm.is_active = 1
                  AND u.company_id IS NOT NULL
                GROUP BY pm.project_id
            ) t ON t.project_id = p.project_id
            SET
                p.company_id = COALESCE(p.company_id, t.company_id),
                p.branch_id = COALESCE(p.branch_id, t.branch_id)
            WHERE p.company_id IS NULL
            """
        )
    )


def downgrade() -> None:
    if _index_exists("projects", "ix_projects_branch_id"):
        op.drop_index("ix_projects_branch_id", table_name="projects")
    if _index_exists("projects", "ix_projects_company_id"):
        op.drop_index("ix_projects_company_id", table_name="projects")

    if _fk_exists("projects", "fk_projects_branch_id_company_branches"):
        op.drop_constraint("fk_projects_branch_id_company_branches", "projects", type_="foreignkey")
    if _fk_exists("projects", "fk_projects_company_id_companies"):
        op.drop_constraint("fk_projects_company_id_companies", "projects", type_="foreignkey")

    if _column_exists("projects", "branch_id"):
        op.drop_column("projects", "branch_id")
    if _column_exists("projects", "company_id"):
        op.drop_column("projects", "company_id")
