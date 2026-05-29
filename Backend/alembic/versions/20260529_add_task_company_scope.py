"""Add company_id to tasks for tenant scoping

Revision ID: add_task_company_scope
Revises: add_office_timing_company_scope
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_task_company_scope"
down_revision = "add_office_timing_company_scope"
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
    if not _column_exists("tasks", "company_id"):
        op.add_column("tasks", sa.Column("company_id", sa.Integer(), nullable=True))

    if not _fk_exists("tasks", "fk_tasks_company_id_companies"):
        op.create_foreign_key(
            "fk_tasks_company_id_companies",
            "tasks",
            "companies",
            ["company_id"],
            ["company_id"],
            ondelete="CASCADE",
        )

    if not _index_exists("tasks", "ix_tasks_company_id"):
        op.create_index("ix_tasks_company_id", "tasks", ["company_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE tasks t
            LEFT JOIN projects p ON p.project_id = t.project_id
            LEFT JOIN users u_to ON u_to.user_id = t.assigned_to
            LEFT JOIN users u_by ON u_by.user_id = t.assigned_by
            SET t.company_id = COALESCE(p.company_id, u_to.company_id, u_by.company_id)
            WHERE t.company_id IS NULL
            """
        )
    )

    op.execute(sa.text("DELETE FROM tasks WHERE company_id IS NULL"))

    op.alter_column("tasks", "company_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    if _column_exists("tasks", "company_id"):
        op.alter_column("tasks", "company_id", existing_type=sa.Integer(), nullable=True)

    if _index_exists("tasks", "ix_tasks_company_id"):
        op.drop_index("ix_tasks_company_id", table_name="tasks")

    if _fk_exists("tasks", "fk_tasks_company_id_companies"):
        op.drop_constraint("fk_tasks_company_id_companies", "tasks", type_="foreignkey")

    if _column_exists("tasks", "company_id"):
        op.drop_column("tasks", "company_id")
