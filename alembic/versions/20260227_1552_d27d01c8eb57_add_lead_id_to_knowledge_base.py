"""add_lead_id_to_knowledge_base

Revision ID: d27d01c8eb57
Revises: c4d5e6f7a8b9
Create Date: 2026-02-27 15:52:11.167083

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd27d01c8eb57'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add lead_id column to knowledge_base
    op.add_column('knowledge_base', sa.Column('lead_id', sa.UUID(), nullable=True))
    
    # Create index on lead_id
    op.create_index(op.f('ix_knowledge_base_lead_id'), 'knowledge_base', ['lead_id'], unique=False)
    
    # Create foreign key constraint
    op.create_foreign_key('fk_knowledge_base_lead_id_leads', 'knowledge_base', 'leads', ['lead_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint('fk_knowledge_base_lead_id_leads', 'knowledge_base', type_='foreignkey')
    
    # Drop index
    op.drop_index(op.f('ix_knowledge_base_lead_id'), table_name='knowledge_base')
    
    # Drop column
    op.drop_column('knowledge_base', 'lead_id')
