"""add crm performance indexes

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-06 13:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_leads_org_status_last_message_at",
        "leads",
        ["org_id", "status", "last_message_at"],
        unique=False,
    )
    op.create_index(
        "ix_leads_org_source",
        "leads",
        ["org_id", "source"],
        unique=False,
    )
    op.create_index(
        "ix_leads_org_followup_scan",
        "leads",
        ["org_id", "status", "followup_count", "last_message_at"],
        unique=False,
    )
    op.create_index(
        "ix_chat_messages_lead_transport_created_at",
        "chat_messages",
        ["lead_id", "transport", "created_at"],
        unique=False,
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_leads_full_name_trgm "
        "ON leads USING gin (full_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_leads_phone_trgm "
        "ON leads USING gin (phone gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_leads_username_trgm "
        "ON leads USING gin (username gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_leads_username_trgm")
    op.execute("DROP INDEX IF EXISTS ix_leads_phone_trgm")
    op.execute("DROP INDEX IF EXISTS ix_leads_full_name_trgm")
    op.drop_index("ix_chat_messages_lead_transport_created_at", table_name="chat_messages")
    op.drop_index("ix_leads_org_followup_scan", table_name="leads")
    op.drop_index("ix_leads_org_source", table_name="leads")
    op.drop_index("ix_leads_org_status_last_message_at", table_name="leads")
