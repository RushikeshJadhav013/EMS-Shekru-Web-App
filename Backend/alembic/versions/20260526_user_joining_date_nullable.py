"""Make users.joining_date nullable without server default

Revision ID: user_joining_date_nullable
Revises: add_meetings_tenant_scope
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "user_joining_date_nullable"
down_revision = "add_meetings_tenant_scope"
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def _column_exists(table: str, column: str) -> bool:
    if table not in _inspector().get_table_names():
        return False
    return column in {col["name"] for col in _inspector().get_columns(table)}


def upgrade() -> None:
    if not _column_exists("users", "joining_date"):
        return
    op.alter_column(
        "users",
        "joining_date",
        existing_type=sa.DateTime(),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    if not _column_exists("users", "joining_date"):
        return
    op.alter_column(
        "users",
        "joining_date",
        existing_type=sa.DateTime(),
        nullable=True,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
