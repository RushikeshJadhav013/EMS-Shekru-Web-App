
"""Create vendors table if it does not exist."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "89119bca2961"
down_revision: Union[str, Sequence[str], None] = "add_salary_slip_history_breakdown"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create vendors table only if it is missing."""

    bind = op.get_bind()
    if "vendors" in inspect(bind).get_table_names():
        return

    op.create_table(
        "vendors",
        sa.Column("vendor_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("vendor_name", sa.String(150), nullable=False),
        sa.Column("contact_person", sa.String(100), nullable=True),
        sa.Column("email", sa.String(150), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
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
    )

    op.create_index(
        "ix_vendors_company_id",
        "vendors",
        ["company_id"],
    )


def downgrade() -> None:
    """Preserve the existing vendors table and data."""
    pass
