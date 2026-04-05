"""add lead lookup status and change history

Revision ID: c9d0e1f2a3b4
Revises: a7b8c9d0e1f2
Create Date: 2026-04-05 22:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    lead_columns = {column["name"] for column in inspector.get_columns("leads")}

    if "telegram_lookup_status" not in lead_columns:
        op.add_column(
            "leads",
            sa.Column("telegram_lookup_status", sa.String(length=32), nullable=False, server_default="not_checked"),
        )
    if "telegram_lookup_checked_at" not in lead_columns:
        op.add_column("leads", sa.Column("telegram_lookup_checked_at", sa.DateTime(timezone=True), nullable=True))
    if "telegram_lookup_error" not in lead_columns:
        op.add_column("leads", sa.Column("telegram_lookup_error", sa.Text(), nullable=True))

    lead_indexes = {index["name"] for index in inspector.get_indexes("leads")}
    if "ix_leads_telegram_lookup_status" not in lead_indexes:
        op.create_index("ix_leads_telegram_lookup_status", "leads", ["telegram_lookup_status"], unique=False)

    if "lead_change_logs" not in tables:
        op.create_table(
            "lead_change_logs",
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("source", sa.String(length=64), nullable=True),
            sa.Column("changes_json", sa.Text(), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_lead_change_logs_id", "lead_change_logs", ["id"], unique=True)
        op.create_index("ix_lead_change_logs_org_id", "lead_change_logs", ["org_id"], unique=False)
        op.create_index("ix_lead_change_logs_lead_id", "lead_change_logs", ["lead_id"], unique=False)
        op.create_index("ix_lead_change_logs_user_id", "lead_change_logs", ["user_id"], unique=False)
        op.create_index("ix_lead_change_logs_action", "lead_change_logs", ["action"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "lead_change_logs" in tables:
        op.drop_index("ix_lead_change_logs_action", table_name="lead_change_logs")
        op.drop_index("ix_lead_change_logs_user_id", table_name="lead_change_logs")
        op.drop_index("ix_lead_change_logs_lead_id", table_name="lead_change_logs")
        op.drop_index("ix_lead_change_logs_org_id", table_name="lead_change_logs")
        op.drop_index("ix_lead_change_logs_id", table_name="lead_change_logs")
        op.drop_table("lead_change_logs")

    lead_columns = {column["name"] for column in inspector.get_columns("leads")}
    lead_indexes = {index["name"] for index in inspector.get_indexes("leads")}
    if "ix_leads_telegram_lookup_status" in lead_indexes:
        op.drop_index("ix_leads_telegram_lookup_status", table_name="leads")
    if "telegram_lookup_error" in lead_columns:
        op.drop_column("leads", "telegram_lookup_error")
    if "telegram_lookup_checked_at" in lead_columns:
        op.drop_column("leads", "telegram_lookup_checked_at")
    if "telegram_lookup_status" in lead_columns:
        op.drop_column("leads", "telegram_lookup_status")
