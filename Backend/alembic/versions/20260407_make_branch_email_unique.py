"""Make branch_email globally unique

Revision ID: make_branch_email_unique
Revises: add_company_branch_subscriptions
Create Date: 2026-04-07
"""

from alembic import op
from sqlalchemy import inspect


revision = "make_branch_email_unique"
down_revision = "add_company_branch_subscriptions"
branch_labels = None
depends_on = None


def _unique_constraint_exists(table: str, name: str) -> bool:
    if table not in inspect(op.get_bind()).get_table_names():
        return False
    return name in {uc["name"] for uc in inspect(op.get_bind()).get_unique_constraints(table)}


def upgrade() -> None:
    op.execute("UPDATE companies SET company_email = lower(company_email)")
    op.execute(
        "UPDATE company_branches SET branch_email = lower(branch_email) WHERE branch_email IS NOT NULL"
    )

    if not _unique_constraint_exists("company_branches", "uq_company_branch_email_global"):
        op.create_unique_constraint(
            "uq_company_branch_email_global",
            "company_branches",
            ["branch_email"],
        )


def downgrade() -> None:
    if _unique_constraint_exists("company_branches", "uq_company_branch_email_global"):
        op.drop_constraint(
            "uq_company_branch_email_global",
            "company_branches",
            type_="unique",
        )
