"""add_custom_fields_table

Revision ID: f75517e8690a
Revises: dec010cd2037
Create Date: 2026-02-08 21:00:19.049530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f75517e8690a'
down_revision: Union[str, None] = 'dec010cd2037'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create custom_fields table (using VARCHAR for field_type to avoid enum conflicts)
    op.create_table(
        'custom_fields',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('field_label', sa.String(length=255), nullable=False),
        sa.Column('field_type', sa.String(length=20), nullable=False),  # text, number, select, boolean
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('display_order', sa.String(length=10), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'field_name', name='uq_org_field_name')
    )
    
    # Create indexes
    op.create_index('ix_custom_fields_org_id', 'custom_fields', ['org_id'])


def downgrade() -> None:
    op.drop_index('ix_custom_fields_org_id', table_name='custom_fields')
    op.drop_table('custom_fields')
