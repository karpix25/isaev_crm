"""add_ai_metadata_to_chat_messages

Revision ID: 8a7f176f0529
Revises: f75517e8690a
Create Date: 2026-02-18 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8a7f176f0529'
down_revision: Union[str, None] = 'f75517e8690a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add ai_metadata column to chat_messages table
    op.add_column('chat_messages', sa.Column('ai_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove ai_metadata column from chat_messages table
    op.drop_column('chat_messages', 'ai_metadata')
