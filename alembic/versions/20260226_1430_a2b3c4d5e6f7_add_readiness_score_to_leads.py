"""add readiness score to leads

Revision ID: a2b3c4d5e6f7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-26 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type if it doesn't exist
    readiness_score_enum = postgresql.ENUM('A', 'B', 'C', name='readiness_score')
    readiness_score_enum.create(op.get_bind(), checkfirst=True)
    
    # Add column to leads table
    op.add_column('leads', sa.Column('readiness_score', sa.Enum('A', 'B', 'C', name='readiness_score'), nullable=True))


def downgrade() -> None:
    # Drop column
    op.drop_column('leads', 'readiness_score')
    
    # Drop enum type
    readiness_score_enum = postgresql.ENUM('A', 'B', 'C', name='readiness_score')
    readiness_score_enum.drop(op.get_bind(), checkfirst=True)
