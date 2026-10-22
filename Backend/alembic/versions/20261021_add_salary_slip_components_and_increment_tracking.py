"""Add component columns to salary_slip_history, tracking fields to salary_increments, and changed_by fields to employee_salary_history.

Revision ID: add_slip_components_and_increment_tracking
Revises: add_employee_salary_history
Create Date: 2026-10-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "add_slip_components_and_increment_tracking"
down_revision = "add_employee_salary_history"
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    existing_tables = set(inspector.get_table_names())

    # 1. Update salary_increments
    if "salary_increments" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("salary_increments")}
        if "effective_month" not in existing_cols:
            op.add_column("salary_increments", sa.Column("effective_month", sa.Integer(), nullable=True))
        if "effective_year" not in existing_cols:
            op.add_column("salary_increments", sa.Column("effective_year", sa.Integer(), nullable=True))
        if "approved_by_name" not in existing_cols:
            op.add_column("salary_increments", sa.Column("approved_by_name", sa.String(150), nullable=True))
        if "approved_by_role" not in existing_cols:
            op.add_column("salary_increments", sa.Column("approved_by_role", sa.String(50), nullable=True))

    # 2. Update employee_salary_history
    if "employee_salary_history" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("employee_salary_history")}
        if "changed_by_name" not in existing_cols:
            op.add_column("employee_salary_history", sa.Column("changed_by_name", sa.String(150), nullable=True))
        if "changed_by_role" not in existing_cols:
            op.add_column("employee_salary_history", sa.Column("changed_by_role", sa.String(50), nullable=True))

    # 3. Update salary_slip_history
    if "salary_slip_history" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("salary_slip_history")}
        if "basic" not in existing_cols:
            op.add_column("salary_slip_history", sa.Column("basic", sa.Float(), nullable=True))
        if "hra" not in existing_cols:
            op.add_column("salary_slip_history", sa.Column("hra", sa.Float(), nullable=True))
        if "special_allowance" not in existing_cols:
            op.add_column("salary_slip_history", sa.Column("special_allowance", sa.Float(), nullable=True))
        if "conveyance" not in existing_cols:
            op.add_column("salary_slip_history", sa.Column("conveyance", sa.Float(), nullable=True))
        if "medical_allowance" not in existing_cols:
            op.add_column("salary_slip_history", sa.Column("medical_allowance", sa.Float(), nullable=True))
        if "other_allowance" not in existing_cols:
            op.add_column("salary_slip_history", sa.Column("other_allowance", sa.Float(), nullable=True))
        if "professional_tax" not in existing_cols:
            op.add_column("salary_slip_history", sa.Column("professional_tax", sa.Float(), nullable=True))
        if "pf" not in existing_cols:
            op.add_column("salary_slip_history", sa.Column("pf", sa.Float(), nullable=True))
        if "variable_pay" not in existing_cols:
            op.add_column("salary_slip_history", sa.Column("variable_pay", sa.Float(), nullable=True, server_default="0"))
        if "salary_history_id" not in existing_cols:
            op.add_column("salary_slip_history", sa.Column("salary_history_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_salary_slip_history_salary_history_id",
                "salary_slip_history",
                "employee_salary_history",
                ["salary_history_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    inspector = _inspector()
    existing_tables = set(inspector.get_table_names())

    if "salary_slip_history" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("salary_slip_history")}
        if "salary_history_id" in existing_cols:
            op.drop_constraint("fk_salary_slip_history_salary_history_id", "salary_slip_history", type_="foreignkey")
            op.drop_column("salary_slip_history", "salary_history_id")
        for col in [
            "variable_pay", "pf", "professional_tax", "other_allowance",
            "medical_allowance", "conveyance", "special_allowance", "hra", "basic"
        ]:
            if col in existing_cols:
                op.drop_column("salary_slip_history", col)

    if "employee_salary_history" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("employee_salary_history")}
        for col in ["changed_by_role", "changed_by_name"]:
            if col in existing_cols:
                op.drop_column("employee_salary_history", col)

    if "salary_increments" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("salary_increments")}
        for col in ["approved_by_role", "approved_by_name", "effective_year", "effective_month"]:
            if col in existing_cols:
                op.drop_column("salary_increments", col)
