"""merge expense and salary migrations

Revision ID: 8d206b940fdb
Revises: add_slip_components_and_increment_tracking, a10d655b71a6
Create Date: 2026-10-26 16:46:35.232779

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d206b940fdb'
down_revision: Union[str, Sequence[str], None] = ('add_slip_components_and_increment_tracking', 'a10d655b71a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
