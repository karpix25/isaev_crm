"""Estimate-related bot actions that must do real work, not just reply."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiogram.types import FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot import bot
from src.models import Lead, MessageStatus, MessageTransport
from src.models.lead import LeadStatus
from src.services.chat_service import chat_service


DEFAULT_ESTIMATE_RESEND_TEXT = (
    "Конечно, отправляю смету еще раз файлом. "
    "Посмотрите, пожалуйста, и если будут вопросы по пунктам — разберем."
)


async def send_ready_estimate_from_crm(db: AsyncSession, message: Message, lead: Lead) -> bool:
    data = _parse_data(lead.extracted_data)
    estimate_request = data.get("estimate_request") if isinstance(data.get("estimate_request"), dict) else {}
    final_file = estimate_request.get("final_file") if isinstance(estimate_request.get("final_file"), dict) else None

    if not final_file or not final_file.get("url"):
        await _reply_and_log(
            db,
            message,
            lead,
            "Пока не вижу готовую смету в карточке. Уточню у команды и вернемся с файлом, как только он будет готов.",
            {"type": "estimate_resend_missing_file"},
        )
        return True

    file_path = _local_media_path(str(final_file["url"]))
    if not file_path.exists():
        await _reply_and_log(
            db,
            message,
            lead,
            "Смета отмечена как готовая, но файл сейчас не нашелся на сервере. Передам менеджеру, чтобы проверили вручную.",
            {"type": "estimate_resend_file_not_found", "file_url": final_file.get("url")},
        )
        return True

    if not bot:
        await _reply_and_log(
            db,
            message,
            lead,
            "Смета готова, но сейчас не получается отправить файл автоматически. Передам менеджеру, чтобы прислали вручную.",
            {"type": "estimate_resend_bot_unavailable", "file_url": final_file.get("url")},
        )
        return True

    sent = await bot.send_document(
        chat_id=message.chat.id,
        document=FSInputFile(file_path),
        caption=DEFAULT_ESTIMATE_RESEND_TEXT,
        business_connection_id=getattr(message, "business_connection_id", None),
        message_thread_id=message.message_thread_id if getattr(message, "is_topic_message", False) else None,
    )

    sent_at = datetime.now(timezone.utc).isoformat()
    estimate_request["status"] = "sent"
    estimate_request["resent_at"] = sent_at
    estimate_request.setdefault("sent_at", sent_at)
    data["estimate_request"] = estimate_request
    lead.extracted_data = json.dumps(data, ensure_ascii=False)
    lead.status = LeadStatus.ESTIMATE_SENT.value
    await db.commit()
    await db.refresh(lead)

    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=DEFAULT_ESTIMATE_RESEND_TEXT,
        media_url=str(final_file["url"]),
        telegram_message_id=sent.message_id,
        sender_name="AI",
        ai_metadata={"source": "ai_tool", "type": "final_estimate_resent"},
        status=MessageStatus.SENT,
        transport=MessageTransport.TELEGRAM,
    )
    return True


def looks_like_estimate_file_request(text: str) -> bool:
    normalized = text.lower().replace("ё", "е")
    if "смет" not in normalized:
        return False
    send_markers = (
        "пришл",
        "отправ",
        "скин",
        "кин",
        "повтор",
        "еще раз",
        "файл",
        "не приш",
        "где",
    )
    return any(marker in normalized for marker in send_markers)


async def _reply_and_log(
    db: AsyncSession,
    message: Message,
    lead: Lead,
    text: str,
    metadata: dict[str, Any],
) -> None:
    sent = await message.answer(text)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=sent.message_id,
        sender_name="AI",
        ai_metadata={"source": "ai_tool", **metadata},
        status=MessageStatus.SENT,
        transport=MessageTransport.TELEGRAM,
    )


def _parse_data(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _local_media_path(url: str) -> Path:
    if not url.startswith("/media/"):
        raise ValueError("unsupported_media_url")
    return Path.cwd() / url.lstrip("/")
