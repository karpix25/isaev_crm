"""Safe CRM read tools for Telegram AI actions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead, MessageStatus, MessageTransport
from src.services.chat_service import chat_service


async def answer_measurement_booking(db: AsyncSession, message: Message, lead: Lead) -> bool:
    measurement = _measurement_data(lead)
    date_text = _format_measurement_start(measurement.get("start"))
    address = str(measurement.get("address") or "").strip()
    has_calendar_booking = bool(str(measurement.get("booking_uid") or "").strip())

    if date_text:
        status_text = "запись закреплена" if has_calendar_booking else "слот выбран, но календарная бронь требует проверки"
        lines = [f"Вижу замер: {date_text}.", f"Статус: {status_text}."]
        if address:
            lines.append(f"Адрес: {address}.")
        lines.append("Если нужно перенести, напишите удобный день.")
        return await _reply_and_log(db, message, lead, "\n".join(lines), "read_measurement_booking")

    return await _reply_and_log(
        db,
        message,
        lead,
        "Активной записи на замер пока не вижу. Можем записать вас на удобное окно.",
        "read_measurement_booking_empty",
    )


async def answer_estimate_status(db: AsyncSession, message: Message, lead: Lead) -> bool:
    estimate = _estimate_request_data(lead)
    status = str(estimate.get("status") or "").strip()
    final_file = estimate.get("final_file") if isinstance(estimate.get("final_file"), dict) else {}

    if status == "sent":
        text = "Смету уже отправляли. Если нужно, могу прислать файл еще раз."
    elif final_file and final_file.get("url"):
        text = "Смета готова и есть в CRM. Могу отправить ее сюда файлом."
    elif status in {"needs_estimate", "preparing"}:
        text = "Смета сейчас в работе. Обычно расчет готовим в течение 24 часов."
    elif status == "ready_to_send":
        text = "Смета готова к отправке. Могу прислать файл сюда."
    else:
        text = "Готовой сметы в карточке пока не вижу. Если вы уже отправляли проект, проверим у сметчика."

    return await _reply_and_log(db, message, lead, text, "read_estimate_status")


async def answer_lead_summary(db: AsyncSession, message: Message, lead: Lead) -> bool:
    data = _parse_data(lead.extracted_data)
    quiz = data.get("quiz") if isinstance(data.get("quiz"), dict) else {}
    answers = quiz.get("answers") if isinstance(quiz.get("answers"), dict) else {}
    measurement = _measurement_data(lead)

    lines = ["Вижу по заявке:"]
    if answers:
        for key, label in (
            ("type", "Объект"),
            ("area", "Площадь"),
            ("rtype", "Ремонт"),
            ("design", "Дизайн-проект"),
        ):
            value = answers.get(key)
            if value:
                lines.append(f"{label}: {_human_quiz_value(key, value)}")
    if lead.phone:
        lines.append(f"Телефон: {lead.phone}")
    measurement_date = _format_measurement_start(measurement.get("start"))
    if measurement_date:
        lines.append(f"Замер: {measurement_date}")
    if len(lines) == 1:
        lines.append("пока заполнено мало данных.")
    return await _reply_and_log(db, message, lead, "\n".join(lines), "read_lead_summary")


def _measurement_data(lead: Lead) -> dict[str, Any]:
    data = _parse_data(lead.extracted_data)
    measurement = data.get("measurement")
    return measurement if isinstance(measurement, dict) else {}


def _estimate_request_data(lead: Lead) -> dict[str, Any]:
    data = _parse_data(lead.extracted_data)
    estimate = data.get("estimate_request")
    return estimate if isinstance(estimate, dict) else {}


async def _reply_and_log(
    db: AsyncSession,
    message: Message,
    lead: Lead,
    text: str,
    tool_type: str,
) -> bool:
    sent = await message.answer(text)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=sent.message_id,
        sender_name="AI",
        ai_metadata={"source": "crm_safe_tool", "type": tool_type},
        status=MessageStatus.SENT,
        transport=MessageTransport.TELEGRAM,
    )
    return True


def _parse_data(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _format_measurement_start(value: Any) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y в %H:%M")
    except Exception:
        return str(value)


def _human_quiz_value(key: str, value: Any) -> str:
    labels = {
        "type": {"flat": "Квартира", "house": "Дом", "commercial": "Коммерция"},
        "area": {"xs": "До 40 м²", "sm": "40-70 м²", "md": "70-100 м²", "lg": "Более 100 м²"},
        "rtype": {"cosm": "Косметический", "finish": "Чистовая отделка", "full": "Под ключ"},
        "design": {"yes": "Проект готов", "wip": "Проект в работе", "no": "Проекта нет"},
    }
    raw = str(value)
    return labels.get(key, {}).get(raw, raw)
