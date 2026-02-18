"""add_avatar_url_to_leads

Revision ID: 659c4b0123a4
Revises: 8a7f176f0529
Create Date: 2026-02-18 20:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '659c4b0123a4'
down_revision: Union[str, None] = '8a7f176f0529'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add avatar_url column to leads table
    op.add_column('leads', sa.Column('avatar_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Remove avatar_url column from leads table
    op.drop_column('leads', 'avatar_url')
