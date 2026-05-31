"""Estimate-related bot actions that must do real work, not just reply."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead, MessageStatus, MessageTransport
from src.models.lead import LeadStatus
from src.services.chat_service import chat_service
from src.services.estimate_delivery_service import estimate_delivery_service
from src.services.media_path_service import media_path_service


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

    file_path = media_path_service.resolve_local_media_path(str(final_file["url"]))
    if not file_path.exists():
        await _reply_and_log(
            db,
            message,
            lead,
            "Смета отмечена как готовая, но файл сейчас не нашелся на сервере. Передам менеджеру, чтобы проверили вручную.",
            {"type": "estimate_resend_file_not_found", "file_url": final_file.get("url")},
        )
        return True

    try:
        telegram_message_id = await estimate_delivery_service.send_telegram_document(
            db=db,
            lead=lead,
            text=DEFAULT_ESTIMATE_RESEND_TEXT,
            file_path=file_path,
        )
    except ValueError as exc:
        await _reply_and_log(
            db,
            message,
            lead,
            "Смета готова, но сейчас не получается отправить файл автоматически. Передам менеджеру, чтобы прислали вручную.",
            {"type": str(exc), "file_url": final_file.get("url")},
        )
        return True

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
        telegram_message_id=telegram_message_id,
        sender_name="AI",
        ai_metadata=_tool_metadata(message, "send_final_estimate", "final_estimate_resent"),
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
        ai_metadata={**_tool_metadata(message, "send_final_estimate", str(metadata.get("type") or "")), **metadata},
        status=MessageStatus.SENT,
        transport=MessageTransport.TELEGRAM,
    )


def _tool_metadata(message: Message, action: str, tool_type: str) -> dict[str, Any]:
    channel = "telegram_business" if getattr(message, "business_connection_id", None) else "telegram"
    return {
        "source": "ai_tool",
        "type": tool_type,
        "crm_tool_action": action,
        "tool_call": {
            "action": action,
            "channel": channel,
        },
    }


def _parse_data(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}
