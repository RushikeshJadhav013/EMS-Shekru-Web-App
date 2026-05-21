"""Add company/branch subscriptions and plan durations

Revision ID: add_company_branch_subscriptions
Revises: add_user_company_branch_scope
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_company_branch_subscriptions"
down_revision = "add_user_company_branch_scope"
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return name in _inspector().get_table_names()


def _column_exists(table: str, column: str) -> bool:
    if not _table_exists(table):
        return False
    return column in {col["name"] for col in _inspector().get_columns(table)}


def _index_exists(table: str, index_name: str) -> bool:
    if not _table_exists(table):
        return False
    return index_name in {idx["name"] for idx in _inspector().get_indexes(table)}


def upgrade() -> None:
    if not _column_exists("subscription_plans", "duration_months"):
        op.add_column(
            "subscription_plans",
            sa.Column("duration_months", sa.Integer(), nullable=False, server_default="12"),
        )

    if not _table_exists("company_subscriptions"):
        op.create_table(
            "company_subscriptions",
            sa.Column("subscription_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column(
                "start_date",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_on",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("updated_on", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.plan_id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["created_by"], ["super_admins.super_admin_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["updated_by"], ["super_admins.super_admin_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("subscription_id"),
            sa.UniqueConstraint("company_id", name="uq_company_subscriptions_company_id"),
        )

    if not _index_exists("company_subscriptions", "ix_company_subscriptions_company_id"):
        op.create_index(
            "ix_company_subscriptions_company_id", "company_subscriptions", ["company_id"], unique=False
        )
    if not _index_exists("company_subscriptions", "ix_company_subscriptions_plan_id"):
        op.create_index(
            "ix_company_subscriptions_plan_id", "company_subscriptions", ["plan_id"], unique=False
        )

    if not _table_exists("branch_subscriptions"):
        op.create_table(
            "branch_subscriptions",
            sa.Column("subscription_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("branch_id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column(
                "start_date",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_on",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("updated_on", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["branch_id"], ["company_branches.branch_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.plan_id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["created_by"], ["super_admins.super_admin_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["updated_by"], ["super_admins.super_admin_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("subscription_id"),
            sa.UniqueConstraint("branch_id", name="uq_branch_subscriptions_branch_id"),
        )

    if not _index_exists("branch_subscriptions", "ix_branch_subscriptions_branch_id"):
        op.create_index(
            "ix_branch_subscriptions_branch_id", "branch_subscriptions", ["branch_id"], unique=False
        )
    if not _index_exists("branch_subscriptions", "ix_branch_subscriptions_plan_id"):
        op.create_index(
            "ix_branch_subscriptions_plan_id", "branch_subscriptions", ["plan_id"], unique=False
        )


def downgrade() -> None:
    if _index_exists("branch_subscriptions", "ix_branch_subscriptions_plan_id"):
        op.drop_index("ix_branch_subscriptions_plan_id", table_name="branch_subscriptions")
    if _index_exists("branch_subscriptions", "ix_branch_subscriptions_branch_id"):
        op.drop_index("ix_branch_subscriptions_branch_id", table_name="branch_subscriptions")
    if _table_exists("branch_subscriptions"):
        op.drop_table("branch_subscriptions")

    if _index_exists("company_subscriptions", "ix_company_subscriptions_plan_id"):
        op.drop_index("ix_company_subscriptions_plan_id", table_name="company_subscriptions")
    if _index_exists("company_subscriptions", "ix_company_subscriptions_company_id"):
        op.drop_index("ix_company_subscriptions_company_id", table_name="company_subscriptions")
    if _table_exists("company_subscriptions"):
        op.drop_table("company_subscriptions")

    if _column_exists("subscription_plans", "duration_months"):
        op.drop_column("subscription_plans", "duration_months")
