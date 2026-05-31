"""add agent tool calls

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-04-06 15:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("args", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("strict_schema", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("executed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("result", sa.String(length=80), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_tool_calls_org_id"), "agent_tool_calls", ["org_id"], unique=False)
    op.create_index(op.f("ix_agent_tool_calls_lead_id"), "agent_tool_calls", ["lead_id"], unique=False)
    op.create_index(op.f("ix_agent_tool_calls_action"), "agent_tool_calls", ["action"], unique=False)
    op.create_index(op.f("ix_agent_tool_calls_executed"), "agent_tool_calls", ["executed"], unique=False)
    op.create_index(op.f("ix_agent_tool_calls_result"), "agent_tool_calls", ["result"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_tool_calls_result"), table_name="agent_tool_calls")
    op.drop_index(op.f("ix_agent_tool_calls_executed"), table_name="agent_tool_calls")
    op.drop_index(op.f("ix_agent_tool_calls_action"), table_name="agent_tool_calls")
    op.drop_index(op.f("ix_agent_tool_calls_lead_id"), table_name="agent_tool_calls")
    op.drop_index(op.f("ix_agent_tool_calls_org_id"), table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")
