"""make_expense_vendor_required

Revision ID: 1eb21f204450
Revises: 19e7b9d418b3
Create Date: 2026-11-03 18:39:41.612140

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1eb21f204450'
down_revision: Union[str, Sequence[str], None] = '19e7b9d418b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove the existing foreign key
    op.drop_constraint(
        "expenses_ibfk_3",
        "expenses",
        type_="foreignkey",
    )

    # Make vendor_id mandatory
    op.alter_column(
        "expenses",
        "vendor_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # Recreate foreign key with RESTRICT
    op.create_foreign_key(
        "expenses_ibfk_3",
        "expenses",
        "vendors",
        ["vendor_id"],
        ["vendor_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Remove the RESTRICT foreign key
    op.drop_constraint(
        "expenses_ibfk_3",
        "expenses",
        type_="foreignkey",
    )

    # Make vendor_id optional again
    op.alter_column(
        "expenses",
        "vendor_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # Restore the original foreign key
    op.create_foreign_key(
        "expenses_ibfk_3",
        "expenses",
        "vendors",
        ["vendor_id"],
        ["vendor_id"],
        ondelete="SET NULL",
    )