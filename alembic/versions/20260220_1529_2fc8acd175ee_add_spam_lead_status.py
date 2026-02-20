"""add_spam_lead_status

Revision ID: 2fc8acd175ee
Revises: 659c4b0123a4
Create Date: 2026-02-20 15:29:01.969252

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2fc8acd175ee'
down_revision: Union[str, None] = '659c4b0123a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add SPAM to the lead_status ENUM
    # Note: postgres doesn't support removing enum values natively without recreating the type,
    # so we use ALTER TYPE ADD VALUE
    op.execute("ALTER TYPE lead_status ADD VALUE IF NOT EXISTS 'SPAM'")


def downgrade() -> None:
    # We cannot easily remove a value from an enum in Postgres.
    # We would have to create a new type, cast the columns, and drop the old type.
    # For now, it's safer to just leave the value if downgrading.
    pass
