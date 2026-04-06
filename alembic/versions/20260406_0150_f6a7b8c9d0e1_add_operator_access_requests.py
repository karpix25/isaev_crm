"""add operator access requests table

Revision ID: f6a7b8c9d0e1
Revises: e4f5a6b7c8d9
Create Date: 2026-04-06 01:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "operator_access_requests" not in tables:
        op.create_table(
            "operator_access_requests",
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("telegram_id", sa.BigInteger(), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column("username", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("processed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.String(length=500), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["processed_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    indexes = {index["name"] for index in inspector.get_indexes("operator_access_requests")}
    if "ix_operator_access_requests_id" not in indexes:
        op.create_index("ix_operator_access_requests_id", "operator_access_requests", ["id"], unique=True)
    if "ix_operator_access_requests_org_id" not in indexes:
        op.create_index("ix_operator_access_requests_org_id", "operator_access_requests", ["org_id"], unique=False)
    if "ix_operator_access_requests_status" not in indexes:
        op.create_index("ix_operator_access_requests_status", "operator_access_requests", ["status"], unique=False)
    if "ix_operator_access_requests_telegram_id" not in indexes:
        op.create_index("ix_operator_access_requests_telegram_id", "operator_access_requests", ["telegram_id"], unique=False)
    if "ix_operator_access_requests_processed_by_user_id" not in indexes:
        op.create_index(
            "ix_operator_access_requests_processed_by_user_id",
            "operator_access_requests",
            ["processed_by_user_id"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "operator_access_requests" not in tables:
        return

    indexes = {index["name"] for index in inspector.get_indexes("operator_access_requests")}
    if "ix_operator_access_requests_processed_by_user_id" in indexes:
        op.drop_index("ix_operator_access_requests_processed_by_user_id", table_name="operator_access_requests")
    if "ix_operator_access_requests_telegram_id" in indexes:
        op.drop_index("ix_operator_access_requests_telegram_id", table_name="operator_access_requests")
    if "ix_operator_access_requests_status" in indexes:
        op.drop_index("ix_operator_access_requests_status", table_name="operator_access_requests")
    if "ix_operator_access_requests_org_id" in indexes:
        op.drop_index("ix_operator_access_requests_org_id", table_name="operator_access_requests")
    if "ix_operator_access_requests_id" in indexes:
        op.drop_index("ix_operator_access_requests_id", table_name="operator_access_requests")
    op.drop_table("operator_access_requests")
