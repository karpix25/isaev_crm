"""add auth sessions table

Revision ID: f1a2b3c4d5e6
Revises: e3f4a5b6c7d8
Create Date: 2026-04-05 01:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "auth_sessions" not in inspector.get_table_names():
        op.create_table(
            "auth_sessions",
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("telegram_id", sa.BigInteger(), nullable=True),
            sa.Column("username", sa.String(length=255), nullable=True),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_auth_sessions_id"), "auth_sessions", ["id"], unique=True)
        op.create_index(op.f("ix_auth_sessions_status"), "auth_sessions", ["status"], unique=False)
        op.create_index(op.f("ix_auth_sessions_telegram_id"), "auth_sessions", ["telegram_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_sessions_telegram_id"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_status"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")

