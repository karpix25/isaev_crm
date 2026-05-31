"""Telegram callbacks for the direct lead inline qualification flow."""

import json

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot import dp
from src.database import AsyncSessionLocal
from src.models import Lead
from src.services.chat_service import chat_service
from src.services.direct_qualification_service import apply_callback_answer


router = Router()


def _lead_extracted_data(lead: Lead) -> dict:
    if not getattr(lead, "extracted_data", None):
        return {}
    try:
        data = json.loads(lead.extracted_data)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


async def _find_lead_by_telegram(db: AsyncSession, telegram_id: int):
    lead_result = await db.execute(
        select(Lead)
        .where(Lead.telegram_id == telegram_id)
        .order_by(Lead.updated_at.desc())
        .limit(1)
    )
    return lead_result.scalar_one_or_none()


@router.callback_query(F.data.regexp(r"^dq:[a-z_]+:[a-z0-9_]+$"))
async def direct_qualification_callback(query: CallbackQuery):
    if not query.from_user:
        await query.answer("Не удалось определить пользователя", show_alert=True)
        return

    async with AsyncSessionLocal() as db:
        lead = await _find_lead_by_telegram(db, query.from_user.id)
        if not lead:
            await query.answer("Заявка не найдена", show_alert=True)
            return

        result = apply_callback_answer(_lead_extracted_data(lead), query.data)
        if not result:
            await query.answer("Не удалось сохранить ответ", show_alert=True)
            return

        lead.extracted_data = json.dumps(result.updated_data, ensure_ascii=False)
        await db.commit()

        await chat_service.save_incoming_message(
            db=db,
            lead_id=lead.id,
            content=f"Ответ в мини-квизе: {result.label}",
            telegram_message_id=query.message.message_id if query.message else None,
            sender_name=query.from_user.full_name,
            ai_metadata={
                "source": "direct_qualification",
                "field": result.field,
                "value": result.value,
            },
        )

        if query.message:
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        if result.next_prompt:
            text = result.next_prompt.text
            reply_markup = result.next_prompt.keyboard
            metadata_type = "question"
        else:
            text = result.completion_text or "Спасибо, сохранили ответ ✅"
            reply_markup = None
            metadata_type = "completed"

        sent_message = None
        if query.message:
            sent_message = await query.message.answer(text, reply_markup=reply_markup)

        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent_message.message_id if sent_message else None,
            sender_name="AI",
            ai_metadata={
                "source": "direct_qualification",
                "type": metadata_type,
                "field": result.next_prompt.field if result.next_prompt else None,
                "skip_knowledge_index": True,
            },
        )
        await query.answer("Сохранил")


dp.include_router(router)
