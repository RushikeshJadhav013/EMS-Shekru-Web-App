"""Add optional deduction and leave breakdown columns to salary_slip_history

Revision ID: add_salary_slip_history_breakdown
Revises: add_user_pin_auth
Create Date: 2026-08-25

Old rows keep existing gross/total_deductions/net values unchanged.
New columns default to NULL/0 so legacy history has no breakdown.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_salary_slip_history_breakdown"
down_revision = "add_user_pin_auth"
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def _column_exists(table: str, column: str) -> bool:
    if table not in _inspector().get_table_names():
        return False
    return column in {col["name"] for col in _inspector().get_columns(table)}


def upgrade() -> None:
    table = "salary_slip_history"
    if table not in _inspector().get_table_names():
        return

    columns = [
        ("optional_deduction_1_label", sa.Column("optional_deduction_1_label", sa.String(120), nullable=True)),
        ("optional_deduction_1_amount", sa.Column("optional_deduction_1_amount", sa.Float(), nullable=True)),
        ("optional_deduction_2_label", sa.Column("optional_deduction_2_label", sa.String(120), nullable=True)),
        ("optional_deduction_2_amount", sa.Column("optional_deduction_2_amount", sa.Float(), nullable=True)),
        ("optional_deduction_3_label", sa.Column("optional_deduction_3_label", sa.String(120), nullable=True)),
        ("optional_deduction_3_amount", sa.Column("optional_deduction_3_amount", sa.Float(), nullable=True)),
        ("optional_deduction_4_label", sa.Column("optional_deduction_4_label", sa.String(120), nullable=True)),
        ("optional_deduction_4_amount", sa.Column("optional_deduction_4_amount", sa.Float(), nullable=True)),
        (
            "manual_leave_days",
            sa.Column("manual_leave_days", sa.Float(), nullable=False, server_default="0"),
        ),
        (
            "manual_leave_amount",
            sa.Column("manual_leave_amount", sa.Float(), nullable=False, server_default="0"),
        ),
    ]
    for name, column in columns:
        if not _column_exists(table, name):
            op.add_column(table, column)


def downgrade() -> None:
    table = "salary_slip_history"
    if table not in _inspector().get_table_names():
        return

    for column in (
        "manual_leave_amount",
        "manual_leave_days",
        "optional_deduction_4_amount",
        "optional_deduction_4_label",
        "optional_deduction_3_amount",
        "optional_deduction_3_label",
        "optional_deduction_2_amount",
        "optional_deduction_2_label",
        "optional_deduction_1_amount",
        "optional_deduction_1_label",
    ):
        if _column_exists(table, column):
            op.drop_column(table, column)
