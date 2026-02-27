"""add message status

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-02-27 01:14:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM type
    message_status = postgresql.ENUM('pending', 'sent', 'failed', name='message_status')
    message_status.create(op.get_bind())
    
    # Add column
    op.add_column('chat_messages', sa.Column('status', sa.Enum('pending', 'sent', 'failed', name='message_status'), nullable=False, server_default='sent'))


def downgrade() -> None:
    # Drop column
    op.drop_column('chat_messages', 'status')
    
    # Drop ENUM type
    message_status = postgresql.ENUM('pending', 'sent', 'failed', name='message_status')
    message_status.drop(op.get_bind())
