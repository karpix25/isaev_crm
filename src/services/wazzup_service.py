from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import ChatMessage, Lead, MessageDirection, MessageStatus, MessageTransport

logger = logging.getLogger(__name__)


class WazzupError(Exception):
    pass


@dataclass
class WazzupIncomingMessage:
    channel_id: str
    chat_id: str
    message_id: Optional[str]
    text: str
    sender_name: Optional[str] = None


@dataclass
class WazzupStatusUpdate:
    message_id: Optional[str]
    status: str


class WazzupService:
    @staticmethod
    def is_configured() -> bool:
        return bool(
            settings.wazzup_enabled
            and settings.wazzup_api_key.strip()
            and settings.wazzup_default_channel_id.strip()
        )

    @staticmethod
    def normalize_phone(value: str | None) -> Optional[str]:
        if not value:
            return None
        digits = re.sub(r"\D", "", str(value))
        if not digits:
            return None
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        if len(digits) == 10:
            digits = "7" + digits
        if len(digits) < 10:
            return None
        return f"+{digits}"

    @staticmethod
    def normalize_phone_digits(value: str | None) -> Optional[str]:
        normalized = WazzupService.normalize_phone(value)
        if not normalized:
            return None
        return re.sub(r"\D", "", normalized)

    async def send_whatsapp_message(self, chat_id: str, text: str, channel_id: str | None = None) -> dict[str, Any]:
        if not self.is_configured():
            raise WazzupError("Wazzup is not configured")

        normalized_chat_id = self.normalize_phone_digits(chat_id)
        if not normalized_chat_id:
            raise WazzupError("Invalid phone/chat id for WhatsApp")

        payload = {
            "channelId": (channel_id or settings.wazzup_default_channel_id).strip(),
            "chatType": "whatsapp",
            "chatId": normalized_chat_id,
            "text": text,
        }
        headers = {
            "Authorization": f"Bearer {settings.wazzup_api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        timeout = max(3, int(settings.wazzup_timeout_seconds))
        url = f"{settings.wazzup_api_base_url.rstrip('/')}/message"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                raise WazzupError(f"Wazzup send failed ({response.status_code}): {response.text}")
            data = response.json() if response.content else {}
            if isinstance(data, list):
                data = data[0] if data else {}
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.TimeoutException as exc:
            raise WazzupError("Wazzup request timeout") from exc
        except httpx.HTTPError as exc:
            raise WazzupError(f"Wazzup HTTP error: {exc}") from exc

    def is_valid_webhook_token(self, token: str | None) -> bool:
        expected = (settings.wazzup_webhook_token or "").strip()
        if not expected:
            return True
        return (token or "").strip() == expected

    def extract_incoming_messages(self, payload: Any) -> list[WazzupIncomingMessage]:
        items: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            for key in ("messages", "message", "events"):
                value = payload.get(key)
                if isinstance(value, list):
                    items.extend([item for item in value if isinstance(item, dict)])
                elif isinstance(value, dict):
                    items.append(value)
        elif isinstance(payload, list):
            items.extend([item for item in payload if isinstance(item, dict)])

        result: list[WazzupIncomingMessage] = []
        for item in items:
            direction = str(item.get("direction") or item.get("type") or "").lower()
            if direction in {"outbound", "out", "sent"}:
                continue

            chat_type = str(item.get("chatType") or item.get("transport") or "").lower()
            if chat_type and "whatsapp" not in chat_type:
                continue

            chat_id = (
                item.get("chatId")
                or item.get("chat_id")
                or item.get("phone")
                or item.get("from")
                or item.get("contact")
            )
            channel_id = item.get("channelId") or item.get("channel_id") or settings.wazzup_default_channel_id
            text = (
                item.get("text")
                or item.get("content")
                or item.get("body")
                or (item.get("message") if isinstance(item.get("message"), str) else "")
            )
            if isinstance(item.get("message"), dict):
                message_obj = item.get("message") or {}
                text = text or message_obj.get("text") or message_obj.get("body") or ""
                chat_id = chat_id or message_obj.get("chatId") or message_obj.get("phone")

            normalized_chat_id = self.normalize_phone_digits(str(chat_id) if chat_id else None)
            normalized_text = str(text or "").strip()
            if not normalized_chat_id or not normalized_text:
                continue

            sender_name = (
                item.get("contactName")
                or item.get("senderName")
                or item.get("fromName")
                or item.get("name")
            )
            message_id = item.get("messageId") or item.get("id") or item.get("msgId")

            result.append(
                WazzupIncomingMessage(
                    channel_id=str(channel_id or ""),
                    chat_id=normalized_chat_id,
                    message_id=str(message_id) if message_id else None,
                    text=normalized_text,
                    sender_name=str(sender_name) if sender_name else None,
                )
            )
        return result

    def extract_status_updates(self, payload: Any) -> list[WazzupStatusUpdate]:
        items: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            for key in ("statuses", "statusUpdates", "status"):
                value = payload.get(key)
                if isinstance(value, list):
                    items.extend([item for item in value if isinstance(item, dict)])
                elif isinstance(value, dict):
                    items.append(value)
            if isinstance(payload.get("message"), dict):
                msg = payload["message"]
                if any(key in msg for key in ("status", "messageStatus")):
                    items.append(msg)
        elif isinstance(payload, list):
            items.extend([item for item in payload if isinstance(item, dict)])

        updates: list[WazzupStatusUpdate] = []
        for item in items:
            status_value = str(item.get("status") or item.get("messageStatus") or "").strip().lower()
            if not status_value:
                continue
            message_id = item.get("messageId") or item.get("id") or item.get("msgId")
            updates.append(
                WazzupStatusUpdate(
                    message_id=str(message_id) if message_id else None,
                    status=status_value,
                )
            )
        return updates

    async def find_lead_by_whatsapp_chat_id(self, db: AsyncSession, org_id, chat_id: str) -> Lead | None:
        digits = self.normalize_phone_digits(chat_id)
        if not digits:
            return None

        tail10 = digits[-10:]
        query = (
            select(Lead)
            .where(
                and_(
                    Lead.org_id == org_id,
                    Lead.phone.is_not(None),
                    or_(
                        Lead.phone.ilike(f"%{digits}%"),
                        Lead.phone.ilike(f"%{tail10}%"),
                    ),
                )
            )
            .order_by(desc(Lead.updated_at))
            .limit(50)
        )
        result = await db.execute(query)
        candidates = result.scalars().all()
        for lead in candidates:
            lead_digits = self.normalize_phone_digits(lead.phone)
            if not lead_digits:
                continue
            if lead_digits == digits or lead_digits.endswith(tail10):
                return lead
        return None

    @staticmethod
    def map_wazzup_status_to_message_status(value: str) -> MessageStatus | None:
        normalized = (value or "").strip().lower()
        if normalized in {"sent", "delivered", "read", "ack", "success"}:
            return MessageStatus.SENT
        if normalized in {"failed", "error", "undelivered", "rejected"}:
            return MessageStatus.FAILED
        return None

    async def apply_status_updates(self, db: AsyncSession, status_updates: list[WazzupStatusUpdate]) -> int:
        updated = 0
        if not status_updates:
            return updated

        result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.transport == MessageTransport.WHATSAPP,
                ChatMessage.direction == MessageDirection.OUTBOUND,
            )
            .order_by(desc(ChatMessage.created_at))
            .limit(500)
        )
        messages = result.scalars().all()

        for status in status_updates:
            mapped = self.map_wazzup_status_to_message_status(status.status)
            if mapped is None or not status.message_id:
                continue
            for message in messages:
                metadata = message.ai_metadata or {}
                external_id = str(metadata.get("wazzup_message_id") or "")
                if external_id and external_id == status.message_id:
                    if message.status != mapped:
                        message.status = mapped
                        updated += 1
                    break
        if updated:
            await db.commit()
        return updated


wazzup_service = WazzupService()
