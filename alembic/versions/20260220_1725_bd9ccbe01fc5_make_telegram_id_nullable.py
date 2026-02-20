"""make telegram_id nullable

Revision ID: bd9ccbe01fc5
Revises: 2fc8acd175ee
Create Date: 2026-02-20 17:25:15.631252

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd9ccbe01fc5'
down_revision: Union[str, None] = '2fc8acd175ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the old unique index on telegram_id
    op.drop_index('ix_leads_telegram_id', table_name='leads')
    
    # 2. Alter telegram_id to be nullable
    op.alter_column('leads', 'telegram_id',
               existing_type=sa.BigInteger(),
               nullable=True)
               
    # 3. Create a non-unique index on telegram_id (since we still query by it)
    op.create_index('ix_leads_telegram_id', 'leads', ['telegram_id'], unique=False)
    
    # 4. Create the new composite unique constraint (org_id, telegram_id)
    op.create_unique_constraint('uq_org_telegram_id', 'leads', ['org_id', 'telegram_id'])


def downgrade() -> None:
    # 1. Drop the composite unique constraint
    op.drop_constraint('uq_org_telegram_id', 'leads', type_='unique')
    
    # 2. Drop the non-unique index
    op.drop_index('ix_leads_telegram_id', table_name='leads')
    
    # 3. Alter telegram_id back to NOT NULL (this might fail if there are genuinely null values now)
    op.alter_column('leads', 'telegram_id',
               existing_type=sa.BigInteger(),
               nullable=False)
               
    # 4. Restore the original unique index on telegram_id
    op.create_index('ix_leads_telegram_id', 'leads', ['telegram_id'], unique=True)
