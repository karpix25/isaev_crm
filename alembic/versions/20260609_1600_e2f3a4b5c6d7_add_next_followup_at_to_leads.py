"""add next followup timestamp to leads

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-09 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("next_followup_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_leads_next_followup_at", "leads", ["next_followup_at"], unique=False)
    op.execute(
        sa.text(
            """
            WITH latest_wait_message AS (
                SELECT DISTINCT ON (cm.lead_id)
                    cm.lead_id,
                    cm.content,
                    cm.created_at
                FROM chat_messages cm
                WHERE cm.direction = 'INBOUND'
                  AND (
                    replace(lower(cm.content), 'ё', 'е') ~ 'не\\s+сдан'
                    OR replace(lower(cm.content), 'ё', 'е') ~ 'ждем\\s+.*(сдач|ключ)'
                    OR replace(lower(cm.content), 'ё', 'е') ~ 'пока\\s+рано'
                    OR replace(lower(cm.content), 'ё', 'е') ~ 'еще\\s+рано'
                  )
                ORDER BY cm.lead_id, cm.created_at DESC
            )
            UPDATE leads l
            SET
                next_followup_at = latest_wait_message.created_at + interval '30 days',
                status = 'KEYS_PENDING',
                followup_count = 0,
                extracted_data = (
                    COALESCE(NULLIF(l.extracted_data, ''), '{}')::jsonb
                    || jsonb_build_object(
                        'followup_pause',
                        jsonb_build_object(
                            'reason', 'keys_or_handover_wait',
                            'source_message', left(latest_wait_message.content, 500),
                            'detected_at', latest_wait_message.created_at,
                            'next_followup_at', latest_wait_message.created_at + interval '30 days',
                            'delay_days', 30,
                            'client_context', 'Клиент ждет сдачу квартиры/дома и пока не готов к замеру.',
                            'followup_goal',
                                'Мягко узнать, появились ли новости по сдаче объекта или получению ключей. Если ключи уже близко, предложить заранее подобрать удобное окно бесплатного замера.'
                        )
                    )
                )::text
            FROM latest_wait_message
            WHERE l.id = latest_wait_message.lead_id
              AND l.next_followup_at IS NULL
              AND l.status NOT IN ('MEASUREMENT_BOOKED', 'CONTRACT', 'WON', 'LOST', 'SPAM')
              AND (l.extracted_data IS NULL OR l.extracted_data ~ '^\\s*\\{');
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_leads_next_followup_at", table_name="leads")
    op.drop_column("leads", "next_followup_at")
