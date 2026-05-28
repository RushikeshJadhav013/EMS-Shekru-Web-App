"""Add WFH notifications table

Revision ID: add_wfh_notifications
Revises: make_branch_email_unique
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_wfh_notifications"
down_revision = "make_branch_email_unique"
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return name in _inspector().get_table_names()


def _index_exists(table: str, index_name: str) -> bool:
    if not _table_exists(table):
        return False
    return index_name in {idx["name"] for idx in _inspector().get_indexes(table)}


def upgrade() -> None:
    if not _table_exists("wfh_notifications"):
        op.create_table(
            "wfh_notifications",
            sa.Column("notification_id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("wfh_id", sa.Integer(), nullable=True),
            sa.Column("notification_type", sa.String(length=100), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["wfh_id"], ["wfh_requests.wfh_id"], ondelete="CASCADE"),
        )

    if not _index_exists("wfh_notifications", "ix_wfh_notifications_notification_id"):
        op.create_index(
            "ix_wfh_notifications_notification_id", "wfh_notifications", ["notification_id"], unique=False
        )


def downgrade() -> None:
    if _index_exists("wfh_notifications", "ix_wfh_notifications_notification_id"):
        op.drop_index("ix_wfh_notifications_notification_id", table_name="wfh_notifications")
    if _table_exists("wfh_notifications"):
        op.drop_table("wfh_notifications")
