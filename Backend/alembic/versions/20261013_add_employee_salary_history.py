"""Add complete salary history snapshots and link increments to snapshots.

Revision ID: add_employee_salary_history
Revises: add_salary_slip_history_breakdown
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "add_employee_salary_history"
down_revision = "add_salary_slip_history_breakdown"
branch_labels = None
depends_on = None

def _inspector():
    return inspect(op.get_bind())

def upgrade() -> None:
    inspector = _inspector()
    if "employee_salary_history" not in inspector.get_table_names():
        op.create_table(
            "employee_salary_history",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
            sa.Column("source_salary_id", sa.Integer(), sa.ForeignKey("employee_salaries.id"), nullable=False),
            sa.Column("basic_annual", sa.Float(), nullable=True),
            sa.Column("hra_annual", sa.Float(), nullable=True),
            sa.Column("special_allowance_annual", sa.Float(), nullable=True),
            sa.Column("conveyance_annual", sa.Float(), nullable=True),
            sa.Column("medical_allowance_annual", sa.Float(), nullable=True),
            sa.Column("other_allowance_annual", sa.Float(), nullable=True),
            sa.Column("professional_tax_annual", sa.Float(), nullable=True),
            sa.Column("other_deduction_annual", sa.Float(), nullable=True),
            sa.Column("pf_annual", sa.Float(), nullable=True),
            sa.Column("package_ctc_annual", sa.Float(), nullable=False),
            sa.Column("pan_number", sa.String(20), nullable=True),
            sa.Column("uan_number", sa.String(20), nullable=True),
            sa.Column("pf_no", sa.String(30), nullable=True),
            sa.Column("bank_name", sa.String(100), nullable=True),
            sa.Column("bank_account", sa.String(50), nullable=True),
            sa.Column("ifsc_code", sa.String(20), nullable=True),
            sa.Column("variable_pay", sa.Float(), nullable=True),
            sa.Column("working_days_per_month", sa.Integer(), nullable=True),
            sa.Column("payment_mode", sa.String(50), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("source_created_at", sa.DateTime(), nullable=True),
            sa.Column("source_updated_at", sa.DateTime(), nullable=True),
            sa.Column("effective_from", sa.DateTime(), nullable=True),
            sa.Column("effective_to", sa.DateTime(), nullable=False),
            sa.Column("change_type", sa.String(50), nullable=False, server_default="increment"),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_employee_salary_history_id", "employee_salary_history", ["id"], unique=False)
        op.create_index("ix_employee_salary_history_user_id", "employee_salary_history", ["user_id"], unique=False)
        op.create_index("ix_employee_salary_history_source_salary_id", "employee_salary_history", ["source_salary_id"], unique=False)
    if "salary_increments" in _inspector().get_table_names():
        columns = {c["name"] for c in _inspector().get_columns("salary_increments")}
        if "salary_history_id" not in columns:
            op.add_column("salary_increments", sa.Column("salary_history_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_salary_increments_salary_history_id_employee_salary_history",
                "salary_increments", "employee_salary_history", ["salary_history_id"], ["id"]
            )
            op.create_index("ix_salary_increments_salary_history_id", "salary_increments", ["salary_history_id"], unique=False)

def downgrade() -> None:
    if "salary_increments" in _inspector().get_table_names():
        columns = {c["name"] for c in _inspector().get_columns("salary_increments")}
        if "salary_history_id" in columns:
            op.drop_index("ix_salary_increments_salary_history_id", table_name="salary_increments")
            op.drop_constraint("fk_salary_increments_salary_history_id_employee_salary_history", "salary_increments", type_="foreignkey")
            op.drop_column("salary_increments", "salary_history_id")
    if "employee_salary_history" in _inspector().get_table_names():
        op.drop_index("ix_employee_salary_history_source_salary_id", table_name="employee_salary_history")
        op.drop_index("ix_employee_salary_history_user_id", table_name="employee_salary_history")
        op.drop_index("ix_employee_salary_history_id", table_name="employee_salary_history")
        op.drop_table("employee_salary_history")
