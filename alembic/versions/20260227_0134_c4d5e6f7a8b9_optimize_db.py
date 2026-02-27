"""optimize db flexibility and indexes

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-02-27 01:34:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Modify Leads 'status' column from ENUM to VARCHAR
    # USING clause converts existing ENUM values to their string representations
    op.execute("ALTER TABLE leads ALTER COLUMN status TYPE varchar(50) USING status::text")
    
    # 2. Modify Leads 'readiness_score' column from ENUM to VARCHAR
    op.execute("ALTER TABLE leads ALTER COLUMN readiness_score TYPE varchar(10) USING readiness_score::text")
    
    # 3. Drop the old ENUM types from the database
    # (Optional, but good practice to keep DB clean if no longer used anywhere else)
    op.execute("DROP TYPE IF EXISTS lead_status")
    op.execute("DROP TYPE IF EXISTS readiness_score")
    
    # 4. Add composite index for chat message history querying
    op.create_index(
        'ix_chat_messages_lead_id_created_at',
        'chat_messages',
        ['lead_id', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    # 1. Remove the composite index
    op.drop_index('ix_chat_messages_lead_id_created_at', table_name='chat_messages')
    
    # 2. Recreate the ENUM types
    op.execute("CREATE TYPE lead_status AS ENUM ('NEW', 'CONSULTING', 'FOLLOW_UP', 'QUALIFIED', 'MEASUREMENT', 'ESTIMATE', 'CONTRACT', 'WON', 'LOST', 'SPAM')")
    op.execute("CREATE TYPE readiness_score AS ENUM ('A', 'B', 'C')")
    
    # 3. Convert VARCHAR back to ENUM
    op.execute("ALTER TABLE leads ALTER COLUMN status TYPE lead_status USING status::lead_status")
    op.execute("ALTER TABLE leads ALTER COLUMN readiness_score TYPE readiness_score USING readiness_score::readiness_score")
