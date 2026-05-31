"""add company facts

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-04-06 14:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="company"),
        sa.Column("value_type", sa.String(length=20), nullable=False, server_default="text"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="scenario"),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("stages", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("questions", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("hint", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "key", name="uq_company_facts_org_key"),
    )
    op.create_index(op.f("ix_company_facts_org_id"), "company_facts", ["org_id"], unique=False)
    op.create_index(op.f("ix_company_facts_category"), "company_facts", ["category"], unique=False)
    op.create_index(op.f("ix_company_facts_priority"), "company_facts", ["priority"], unique=False)
    op.create_index(op.f("ix_company_facts_is_active"), "company_facts", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_company_facts_is_active"), table_name="company_facts")
    op.drop_index(op.f("ix_company_facts_priority"), table_name="company_facts")
    op.drop_index(op.f("ix_company_facts_category"), table_name="company_facts")
    op.drop_index(op.f("ix_company_facts_org_id"), table_name="company_facts")
    op.drop_table("company_facts")
