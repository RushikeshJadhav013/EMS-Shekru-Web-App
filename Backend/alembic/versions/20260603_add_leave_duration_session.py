"""Add duration_days and leave_session to leaves for unpaid half-day support

Revision ID: add_leave_duration_session
Revises: add_department_company_scope
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_leave_duration_session"
down_revision = "add_department_company_scope"
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def _column_exists(table: str, column: str) -> bool:
    if table not in _inspector().get_table_names():
        return False
    return column in {col["name"] for col in _inspector().get_columns(table)}


def upgrade() -> None:
    if not _column_exists("leaves", "duration_days"):
        op.add_column(
            "leaves",
            sa.Column("duration_days", sa.Numeric(3, 1), nullable=False, server_default="1.0"),
        )
    if not _column_exists("leaves", "leave_session"):
        op.add_column(
            "leaves",
            sa.Column("leave_session", sa.String(20), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("leaves", "leave_session"):
        op.drop_column("leaves", "leave_session")
    if _column_exists("leaves", "duration_days"):
        op.drop_column("leaves", "duration_days")
