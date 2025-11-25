"""Add work summary and report columns to attendances

Revision ID: add_work_summary_report
Revises: 
Create Date: 2025-11-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_work_summary_report"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attendances", sa.Column("work_summary", sa.Text(), nullable=True))
    op.add_column("attendances", sa.Column("work_report", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("attendances", "work_report")
    op.drop_column("attendances", "work_summary")

