"""Telegram callbacks for the direct lead inline qualification flow."""

import json
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot import dp
from src.bot.measurement_slots import build_measurement_date_keyboard
from src.database import AsyncSessionLocal
from src.models import Lead
from src.models.lead import LeadStatus
from src.services.cal_pro_service import cal_pro_service
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


def _needs_measurement_booking(extracted_data: dict) -> bool:
    return str(extracted_data.get("design_project_status") or "").strip().lower() == "нет"


async def _build_completion_reply(db: AsyncSession, lead: Lead, extracted_data: dict):
    if not _needs_measurement_booking(extracted_data):
        return (
            "Спасибо, вводные собрали ✅\n\n"
            "Теперь менеджер увидит картину сразу и сможет сориентировать без повторных вопросов.",
            None,
            "completed",
        )

    slots = await cal_pro_service.get_slots(days_ahead=7, limit=80)
    if not slots:
        measurement = extracted_data.get("measurement") if isinstance(extracted_data.get("measurement"), dict) else {}
        measurement["status"] = "awaiting_manual_slot"
        measurement["requested_at"] = datetime.now(timezone.utc).isoformat()
        extracted_data["measurement"] = measurement
        lead.extracted_data = json.dumps(extracted_data, ensure_ascii=False)
        lead.status = LeadStatus.MEASUREMENT_PENDING.value
        await db.commit()
        return (
            "Спасибо, вводные собрали ✅\n\n"
            "Раз проекта пока нет, лучше начать с бесплатного замера. "
            "Напишите удобный день и время — менеджер проверит расписание и подтвердит окно.",
            None,
            "measurement_slots_empty",
        )

    measurement = extracted_data.get("measurement") if isinstance(extracted_data.get("measurement"), dict) else {}
    measurement["status"] = "awaiting_slot"
    measurement["requested_at"] = datetime.now(timezone.utc).isoformat()
    extracted_data["measurement"] = measurement
    lead.extracted_data = json.dumps(extracted_data, ensure_ascii=False)
    lead.status = LeadStatus.MEASUREMENT_PENDING.value
    await db.commit()

    return (
        "Спасибо, вводные собрали ✅\n\n"
        "Раз проекта пока нет, лучше начать с бесплатного замера. "
        "Выберите удобный день, а после выезда мы точнее посчитаем работы без стройматериалов 📍",
        build_measurement_date_keyboard(slots),
        "measurement_slots",
    )


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
            content=result.label,
            telegram_message_id=query.message.message_id if query.message else None,
            sender_name=query.from_user.full_name,
            ai_metadata={
                "source": "direct_qualification",
                "field": result.field,
                "value": result.value,
            },
        )

        if result.next_prompt:
            text = result.next_prompt.text
            reply_markup = result.next_prompt.keyboard
            metadata_type = "question"
        else:
            text, reply_markup, metadata_type = await _build_completion_reply(db, lead, result.updated_data)

        if query.message:
            try:
                current_text = query.message.text or ""
                answer_line = f"Ответ: {result.label} ✅"
                edited_text = f"{current_text}\n\n{answer_line}" if current_text else answer_line
                await query.message.edit_text(edited_text, reply_markup=None)
            except Exception:
                pass

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
