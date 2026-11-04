
"""Add expenses table migration.

Revision ID: 0498585f945c
Revises: 89119bca2961
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0498585f945c"
down_revision: Union[str, Sequence[str], None] = "89119bca2961"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create expenses table only if it does not already exist."""

    bind = op.get_bind()
    inspector = inspect(bind)

    if "expenses" in inspector.get_table_names():
        return

    op.create_table(
        "expenses",
        sa.Column("expense_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("sub_category", sa.String(length=100), nullable=True),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("gst_number", sa.String(length=20), nullable=True),
        sa.Column("gst_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("cost_center", sa.String(length=100), nullable=True),
        sa.Column("project_name", sa.String(length=150), nullable=True),
        sa.Column("client_name", sa.String(length=150), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="Pending",
        ),
        sa.Column("approved_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("payment_mode", sa.String(length=50), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("transaction_reference", sa.String(length=150), nullable=True),
        sa.Column(
            "payment_status",
            sa.String(length=50),
            nullable=False,
            server_default="Pending",
        ),
        sa.Column("paid_by", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.company_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.vendor_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.user_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["paid_by"],
            ["users.user_id"],
            ondelete="SET NULL",
        ),
    )

    op.create_index("ix_expenses_company_id", "expenses", ["company_id"])
    op.create_index("ix_expenses_user_id", "expenses", ["user_id"])
    op.create_index("ix_expenses_vendor_id", "expenses", ["vendor_id"])
    op.create_index("ix_expenses_status", "expenses", ["status"])


def downgrade() -> None:
    """Do not drop an existing expenses table or its data."""
    pass
