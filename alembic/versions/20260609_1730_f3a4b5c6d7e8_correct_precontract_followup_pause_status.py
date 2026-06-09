"""correct precontract followup pause status

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-06-09 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE leads
            SET status = 'FOLLOW_UP'
            WHERE status = 'KEYS_PENDING'
              AND next_followup_at IS NOT NULL
              AND (extracted_data IS NULL OR extracted_data ~ '^\\s*\\{')
              AND COALESCE(NULLIF(extracted_data, ''), '{}')::jsonb @>
                  '{"followup_pause": {"reason": "keys_or_handover_wait"}}'::jsonb;
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE leads
            SET status = 'KEYS_PENDING'
            WHERE status = 'FOLLOW_UP'
              AND next_followup_at IS NOT NULL
              AND (extracted_data IS NULL OR extracted_data ~ '^\\s*\\{')
              AND COALESCE(NULLIF(extracted_data, ''), '{}')::jsonb @>
                  '{"followup_pause": {"reason": "keys_or_handover_wait"}}'::jsonb;
            """
        )
    )
