"""add funnel analytics

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-04-06 13:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "funnel_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_token", sa.String(length=64), nullable=False),
        sa.Column("funnel_name", sa.String(length=100), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_step", sa.String(length=100), nullable=True),
        sa.Column("utm_source", sa.String(length=255), nullable=True),
        sa.Column("utm_medium", sa.String(length=255), nullable=True),
        sa.Column("utm_campaign", sa.String(length=255), nullable=True),
        sa.Column("utm_content", sa.String(length=255), nullable=True),
        sa.Column("utm_term", sa.String(length=255), nullable=True),
        sa.Column("entry_url", sa.String(length=1000), nullable=True),
        sa.Column("referrer", sa.String(length=1000), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token"),
    )
    op.create_index("ix_funnel_sessions_id", "funnel_sessions", ["id"], unique=True)
    op.create_index("ix_funnel_sessions_org_id", "funnel_sessions", ["org_id"], unique=False)
    op.create_index("ix_funnel_sessions_lead_id", "funnel_sessions", ["lead_id"], unique=False)
    op.create_index("ix_funnel_sessions_session_token", "funnel_sessions", ["session_token"], unique=True)
    op.create_index("ix_funnel_sessions_funnel_name", "funnel_sessions", ["funnel_name"], unique=False)
    op.create_index("ix_funnel_sessions_channel", "funnel_sessions", ["channel"], unique=False)
    op.create_index("ix_funnel_sessions_source", "funnel_sessions", ["source"], unique=False)
    op.create_index("ix_funnel_sessions_status", "funnel_sessions", ["status"], unique=False)
    op.create_index("ix_funnel_sessions_utm_source", "funnel_sessions", ["utm_source"], unique=False)
    op.create_index("ix_funnel_sessions_utm_campaign", "funnel_sessions", ["utm_campaign"], unique=False)
    op.create_index("ix_funnel_sessions_last_event_at", "funnel_sessions", ["last_event_at"], unique=False)
    op.create_index("ix_funnel_sessions_org_status_last_event", "funnel_sessions", ["org_id", "status", "last_event_at"], unique=False)
    op.create_index("ix_funnel_sessions_org_source_created", "funnel_sessions", ["org_id", "source", "created_at"], unique=False)

    op.create_table(
        "funnel_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("step_id", sa.String(length=100), nullable=True),
        sa.Column("event_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["funnel_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_funnel_events_id", "funnel_events", ["id"], unique=True)
    op.create_index("ix_funnel_events_org_id", "funnel_events", ["org_id"], unique=False)
    op.create_index("ix_funnel_events_session_id", "funnel_events", ["session_id"], unique=False)
    op.create_index("ix_funnel_events_lead_id", "funnel_events", ["lead_id"], unique=False)
    op.create_index("ix_funnel_events_event_type", "funnel_events", ["event_type"], unique=False)
    op.create_index("ix_funnel_events_step_id", "funnel_events", ["step_id"], unique=False)
    op.create_index("ix_funnel_events_org_event_created", "funnel_events", ["org_id", "event_type", "created_at"], unique=False)
    op.create_index("ix_funnel_events_session_created", "funnel_events", ["session_id", "created_at"], unique=False)
    op.create_index("ix_funnel_events_org_step_created", "funnel_events", ["org_id", "step_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_funnel_events_org_step_created", table_name="funnel_events")
    op.drop_index("ix_funnel_events_session_created", table_name="funnel_events")
    op.drop_index("ix_funnel_events_org_event_created", table_name="funnel_events")
    op.drop_index("ix_funnel_events_step_id", table_name="funnel_events")
    op.drop_index("ix_funnel_events_event_type", table_name="funnel_events")
    op.drop_index("ix_funnel_events_lead_id", table_name="funnel_events")
    op.drop_index("ix_funnel_events_session_id", table_name="funnel_events")
    op.drop_index("ix_funnel_events_org_id", table_name="funnel_events")
    op.drop_index("ix_funnel_events_id", table_name="funnel_events")
    op.drop_table("funnel_events")

    op.drop_index("ix_funnel_sessions_org_source_created", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_org_status_last_event", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_last_event_at", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_utm_campaign", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_utm_source", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_status", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_source", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_channel", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_funnel_name", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_session_token", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_lead_id", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_org_id", table_name="funnel_sessions")
    op.drop_index("ix_funnel_sessions_id", table_name="funnel_sessions")
    op.drop_table("funnel_sessions")
