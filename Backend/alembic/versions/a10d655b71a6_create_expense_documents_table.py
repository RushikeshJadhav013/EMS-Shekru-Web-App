
"""Create expense_documents table if it does not exist."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "a10d655b71a6"
down_revision: Union[str, Sequence[str], None] = "0498585f945c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create expense_documents only if the table is missing."""

    bind = op.get_bind()
    if "expense_documents" in inspect(bind).get_table_names():
        return

    op.create_table(
        "expense_documents",
        sa.Column("document_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("document_name", sa.String(255), nullable=False),
        sa.Column("document_path", sa.String(500), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.expense_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.user_id"],
            ondelete="SET NULL",
        ),
    )

    op.create_index(
        "ix_expense_documents_expense_id",
        "expense_documents",
        ["expense_id"],
    )


def downgrade() -> None:
    """Preserve existing expense documents and their data."""
    pass
