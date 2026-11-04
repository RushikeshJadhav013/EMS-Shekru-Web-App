
"""add_is_deleted_to_vendor

Revision ID: 19e7b9d418b3
Revises: a10d655b71a6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "19e7b9d418b3"
down_revision: Union[str, Sequence[str], None] = "a10d655b71a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vendors",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.create_index(
        "ix_vendors_is_deleted",
        "vendors",
        ["is_deleted"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vendors_is_deleted",
        table_name="vendors",
    )

    op.drop_column("vendors", "is_deleted")
