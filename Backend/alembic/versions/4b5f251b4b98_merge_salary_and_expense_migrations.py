"""merge salary and expense migrations

Revision ID: 4b5f251b4b98
Revises: 1eb21f204450, add_slip_components_and_increment_tracking
Create Date: 2026-11-03 19:11:01.898341

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b5f251b4b98'
down_revision: Union[str, Sequence[str], None] = ('1eb21f204450', 'add_slip_components_and_increment_tracking')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
