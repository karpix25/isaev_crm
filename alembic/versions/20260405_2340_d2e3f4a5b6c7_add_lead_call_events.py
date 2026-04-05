"""add lead call events

Revision ID: d2e3f4a5b6c7
Revises: c9d0e1f2a3b4
Create Date: 2026-04-05 23:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "lead_call_events" not in tables:
        op.create_table(
            "lead_call_events",
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("initiated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("operator_phone", sa.String(length=32), nullable=False),
            sa.Column("contact_phone", sa.String(length=32), nullable=False),
            sa.Column("external_id", sa.String(length=128), nullable=False),
            sa.Column("call_session_id", sa.String(length=64), nullable=True),
            sa.Column("call_status", sa.String(length=32), nullable=False, server_default="initiated"),
            sa.Column("disposition", sa.String(length=64), nullable=True),
            sa.Column("record_link", sa.Text(), nullable=True),
            sa.Column("call_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("call_ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("business_card_message", sa.Text(), nullable=True),
            sa.Column("business_card_status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("business_card_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("business_card_error", sa.Text(), nullable=True),
            sa.Column("novofon_response_json", sa.Text(), nullable=True),
            sa.Column("webhook_payload_json", sa.Text(), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("external_id"),
        )
        op.create_index("ix_lead_call_events_id", "lead_call_events", ["id"], unique=True)
        op.create_index("ix_lead_call_events_org_id", "lead_call_events", ["org_id"], unique=False)
        op.create_index("ix_lead_call_events_lead_id", "lead_call_events", ["lead_id"], unique=False)
        op.create_index("ix_lead_call_events_initiated_by_user_id", "lead_call_events", ["initiated_by_user_id"], unique=False)
        op.create_index("ix_lead_call_events_operator_phone", "lead_call_events", ["operator_phone"], unique=False)
        op.create_index("ix_lead_call_events_contact_phone", "lead_call_events", ["contact_phone"], unique=False)
        op.create_index("ix_lead_call_events_external_id", "lead_call_events", ["external_id"], unique=True)
        op.create_index("ix_lead_call_events_call_session_id", "lead_call_events", ["call_session_id"], unique=False)
        op.create_index("ix_lead_call_events_call_status", "lead_call_events", ["call_status"], unique=False)
        op.create_index("ix_lead_call_events_business_card_status", "lead_call_events", ["business_card_status"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "lead_call_events" in tables:
        op.drop_index("ix_lead_call_events_business_card_status", table_name="lead_call_events")
        op.drop_index("ix_lead_call_events_call_status", table_name="lead_call_events")
        op.drop_index("ix_lead_call_events_call_session_id", table_name="lead_call_events")
        op.drop_index("ix_lead_call_events_external_id", table_name="lead_call_events")
        op.drop_index("ix_lead_call_events_contact_phone", table_name="lead_call_events")
        op.drop_index("ix_lead_call_events_operator_phone", table_name="lead_call_events")
        op.drop_index("ix_lead_call_events_initiated_by_user_id", table_name="lead_call_events")
        op.drop_index("ix_lead_call_events_lead_id", table_name="lead_call_events")
        op.drop_index("ix_lead_call_events_org_id", table_name="lead_call_events")
        op.drop_index("ix_lead_call_events_id", table_name="lead_call_events")
        op.drop_table("lead_call_events")
