"""add message transport for chat messages

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-04-06 12:35:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_enums = {
        enum["name"] for enum in inspector.get_enums()
    }
    if "message_transport" not in existing_enums:
        op.execute("CREATE TYPE message_transport AS ENUM ('telegram', 'whatsapp')")

    columns = {column["name"] for column in inspector.get_columns("chat_messages")}
    if "transport" not in columns:
        op.add_column(
            "chat_messages",
            sa.Column(
                "transport",
                sa.Enum("telegram", "whatsapp", name="message_transport"),
                nullable=False,
                server_default="telegram",
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("chat_messages")}
    if "transport" in columns:
        op.drop_column("chat_messages", "transport")

    existing_enums = {enum["name"] for enum in inspector.get_enums()}
    if "message_transport" in existing_enums:
        op.execute("DROP TYPE message_transport")
