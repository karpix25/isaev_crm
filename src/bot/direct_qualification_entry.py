"""Early Telegram entry point for chat-native lead qualification."""

from __future__ import annotations

import json
from typing import Any

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead
from src.services.chat_service import chat_service
from src.services.direct_qualification_service import (
    build_next_prompt,
    mark_prompt_sent,
    should_autostart_qualification,
)
from src.services.measurement_analytics_service import measurement_analytics_service


def _lead_data(lead: Lead) -> dict[str, Any]:
    raw = getattr(lead, "extracted_data", None)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def maybe_start_direct_qualification(
    *,
    db: AsyncSession,
    message: Message,
    lead: Lead,
    stage_context: Any,
    company_name: str,
) -> bool:
    data = _lead_data(lead)
    next_action = str(getattr(stage_context, "next_action", "") or "")
    if not should_autostart_qualification(next_action, data):
        return False

    prompt = build_next_prompt(data, company_name=company_name)
    if not prompt:
        return False

    updated_data = mark_prompt_sent(
        data,
        field=prompt.field,
        source="telegram_direct_entry",
    )
    lead.extracted_data = json.dumps(updated_data, ensure_ascii=False)
    await db.commit()

    sent_message = await message.answer(prompt.text, reply_markup=prompt.keyboard)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=prompt.text,
        telegram_message_id=sent_message.message_id,
        sender_name="AI",
        ai_metadata={
            "source": "direct_qualification",
            "type": "autostart_prompt",
            "field": prompt.field,
            "skip_knowledge_index": True,
        },
    )
    await measurement_analytics_service.record_event(
        db=db,
        lead=lead,
        event_type="telegram_direct_quiz_started",
        source="telegram_direct_entry",
        event_data={
            "field": prompt.field,
            "next_action": next_action,
        },
    )
    return True
