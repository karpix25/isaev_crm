"""remove novofon integration artifacts

Revision ID: b7c8d9e0f1a2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-06 02:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "lead_call_events" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("lead_call_events")}
        if "ix_lead_call_events_business_card_status" in indexes:
            op.drop_index("ix_lead_call_events_business_card_status", table_name="lead_call_events")
        if "ix_lead_call_events_call_status" in indexes:
            op.drop_index("ix_lead_call_events_call_status", table_name="lead_call_events")
        if "ix_lead_call_events_call_session_id" in indexes:
            op.drop_index("ix_lead_call_events_call_session_id", table_name="lead_call_events")
        if "ix_lead_call_events_external_id" in indexes:
            op.drop_index("ix_lead_call_events_external_id", table_name="lead_call_events")
        if "ix_lead_call_events_contact_phone" in indexes:
            op.drop_index("ix_lead_call_events_contact_phone", table_name="lead_call_events")
        if "ix_lead_call_events_operator_phone" in indexes:
            op.drop_index("ix_lead_call_events_operator_phone", table_name="lead_call_events")
        if "ix_lead_call_events_initiated_by_user_id" in indexes:
            op.drop_index("ix_lead_call_events_initiated_by_user_id", table_name="lead_call_events")
        if "ix_lead_call_events_lead_id" in indexes:
            op.drop_index("ix_lead_call_events_lead_id", table_name="lead_call_events")
        if "ix_lead_call_events_org_id" in indexes:
            op.drop_index("ix_lead_call_events_org_id", table_name="lead_call_events")
        if "ix_lead_call_events_id" in indexes:
            op.drop_index("ix_lead_call_events_id", table_name="lead_call_events")
        op.drop_table("lead_call_events")

    org_columns = {column["name"] for column in inspector.get_columns("organizations")}
    if "novofon_business_card_telegram" in org_columns:
        op.drop_column("organizations", "novofon_business_card_telegram")
    if "novofon_business_card_site_url" in org_columns:
        op.drop_column("organizations", "novofon_business_card_site_url")
    if "novofon_business_card_template" in org_columns:
        op.drop_column("organizations", "novofon_business_card_template")
    if "novofon_default_operator_phone" in org_columns:
        op.drop_column("organizations", "novofon_default_operator_phone")
    if "novofon_dial_url_template" in org_columns:
        op.drop_column("organizations", "novofon_dial_url_template")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    org_columns = {column["name"] for column in inspector.get_columns("organizations")}
    tables = set(inspector.get_table_names())

    if "novofon_dial_url_template" not in org_columns:
        op.add_column("organizations", sa.Column("novofon_dial_url_template", sa.String(length=255), nullable=True))
    if "novofon_default_operator_phone" not in org_columns:
        op.add_column("organizations", sa.Column("novofon_default_operator_phone", sa.String(length=32), nullable=True))
    if "novofon_business_card_template" not in org_columns:
        op.add_column("organizations", sa.Column("novofon_business_card_template", sa.String(length=5000), nullable=True))
    if "novofon_business_card_site_url" not in org_columns:
        op.add_column("organizations", sa.Column("novofon_business_card_site_url", sa.String(length=500), nullable=True))
    if "novofon_business_card_telegram" not in org_columns:
        op.add_column("organizations", sa.Column("novofon_business_card_telegram", sa.String(length=255), nullable=True))

    if "lead_call_events" not in tables:
        op.create_table(
            "lead_call_events",
            sa.Column("org_id", sa.UUID(), nullable=False),
            sa.Column("lead_id", sa.UUID(), nullable=False),
            sa.Column("initiated_by_user_id", sa.UUID(), nullable=True),
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
            sa.Column("id", sa.UUID(), nullable=False),
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
