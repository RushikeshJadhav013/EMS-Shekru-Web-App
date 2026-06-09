"""Add PIN auth columns to users

Revision ID: add_user_pin_auth
Revises: add_leave_duration_session
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_user_pin_auth"
down_revision = "add_leave_duration_session"
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def _column_exists(table: str, column: str) -> bool:
    if table not in _inspector().get_table_names():
        return False
    return column in {col["name"] for col in _inspector().get_columns(table)}


def upgrade() -> None:
    if not _column_exists("users", "pin_hash"):
        op.add_column("users", sa.Column("pin_hash", sa.String(length=255), nullable=True))
    if not _column_exists("users", "is_pin_set"):
        op.add_column(
            "users",
            sa.Column("is_pin_set", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _column_exists("users", "pin_set_at"):
        op.add_column("users", sa.Column("pin_set_at", sa.DateTime(), nullable=True))
    if not _column_exists("users", "pin_failed_attempts"):
        op.add_column(
            "users",
            sa.Column("pin_failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _column_exists("users", "pin_locked_until"):
        op.add_column("users", sa.Column("pin_locked_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for column in (
        "pin_locked_until",
        "pin_failed_attempts",
        "pin_set_at",
        "is_pin_set",
        "pin_hash",
    ):
        if _column_exists("users", column):
            op.drop_column("users", column)
