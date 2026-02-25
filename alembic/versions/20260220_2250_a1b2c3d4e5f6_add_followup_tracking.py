"""add followup tracking to leads

Revision ID: a1b2c3d4e5f6
Revises: bd9ccbe01fc5
Create Date: 2026-02-20 22:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'bd9ccbe01fc5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('followup_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('last_followup_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'last_followup_at')
    op.drop_column('leads', 'followup_count')
