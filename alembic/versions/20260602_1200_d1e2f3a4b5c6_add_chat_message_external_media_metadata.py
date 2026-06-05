"""add chat message external and media metadata

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-02 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("chat_messages")}

    new_columns = {
        "media_filename": sa.Column("media_filename", sa.String(length=255), nullable=True),
        "media_mimetype": sa.Column("media_mimetype", sa.String(length=100), nullable=True),
        "media_size": sa.Column("media_size", sa.BigInteger(), nullable=True),
        "external_provider": sa.Column("external_provider", sa.String(length=50), nullable=True),
        "external_message_id": sa.Column("external_message_id", sa.String(length=255), nullable=True),
        "external_chat_id": sa.Column("external_chat_id", sa.String(length=255), nullable=True),
    }
    for name, column in new_columns.items():
        if name not in columns:
            op.add_column("chat_messages", column)

    indexes = {index["name"] for index in inspector.get_indexes("chat_messages")}
    if "ix_chat_messages_external_chat_id" not in indexes:
        op.create_index(
            "ix_chat_messages_external_chat_id",
            "chat_messages",
            ["external_chat_id"],
            unique=False,
        )
    if "ux_chat_messages_external_provider_message_id" not in indexes:
        op.create_index(
            "ux_chat_messages_external_provider_message_id",
            "chat_messages",
            ["external_provider", "external_message_id"],
            unique=True,
            postgresql_where=sa.text(
                "external_provider IS NOT NULL AND external_message_id IS NOT NULL"
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = {index["name"] for index in inspector.get_indexes("chat_messages")}

    if "ux_chat_messages_external_provider_message_id" in indexes:
        op.drop_index("ux_chat_messages_external_provider_message_id", table_name="chat_messages")
    if "ix_chat_messages_external_chat_id" in indexes:
        op.drop_index("ix_chat_messages_external_chat_id", table_name="chat_messages")

    columns = {column["name"] for column in inspector.get_columns("chat_messages")}
    for name in (
        "external_chat_id",
        "external_message_id",
        "external_provider",
        "media_size",
        "media_mimetype",
        "media_filename",
    ):
        if name in columns:
            op.drop_column("chat_messages", name)
