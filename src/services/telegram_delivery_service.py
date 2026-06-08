from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead, MessageStatus
from src.services.user_bot_service import user_bot_service


@dataclass(frozen=True)
class TelegramDeliveryResult:
    status: MessageStatus
    telegram_message_id: int | None
    provider: str
    external_chat_id: str | None = None


class TelegramDeliveryService:
    async def send_text(
        self,
        db: AsyncSession,
        *,
        lead: Lead,
        text: str,
    ) -> TelegramDeliveryResult:
        if not lead.telegram_id:
            raise ValueError("lead_has_no_telegram")

        business_chat = self._business_chat_data(lead)
        if business_chat:
            message_id = await self._send_business_bot_text(
                text=text,
                business_chat=business_chat,
            )
            return TelegramDeliveryResult(
                status=MessageStatus.SENT,
                telegram_message_id=message_id,
                provider="telegram_business_bot",
                external_chat_id=str(business_chat["chat_id"]),
            )

        if lead.source in {"userbot", "CRM"}:
            await user_bot_service.send_message(
                db=db,
                org_id=lead.org_id,
                telegram_id=int(lead.telegram_id),
                text=text,
                username=lead.username,
            )
            return TelegramDeliveryResult(
                status=MessageStatus.SENT,
                telegram_message_id=None,
                provider="telegram_userbot",
                external_chat_id=str(lead.telegram_id),
            )

        message_id = await self._send_official_bot_text(
            telegram_id=int(lead.telegram_id),
            text=text,
        )
        return TelegramDeliveryResult(
            status=MessageStatus.SENT,
            telegram_message_id=message_id,
            provider="telegram_bot",
            external_chat_id=str(lead.telegram_id),
        )

    async def _send_business_bot_text(
        self,
        *,
        text: str,
        business_chat: dict[str, Any],
    ) -> int:
        from src.bot import bot

        if not bot:
            raise ValueError("telegram_bot_unavailable")

        sent = await bot.send_message(
            chat_id=int(business_chat["chat_id"]),
            text=text,
            business_connection_id=str(business_chat["business_connection_id"]),
        )
        return sent.message_id

    async def _send_official_bot_text(self, *, telegram_id: int, text: str) -> int:
        from src.bot import bot

        if not bot:
            raise ValueError("telegram_bot_unavailable")

        sent = await bot.send_message(chat_id=telegram_id, text=text)
        return sent.message_id

    def _business_chat_data(self, lead: Lead) -> dict[str, Any] | None:
        try:
            data = json.loads(lead.extracted_data or "{}")
        except json.JSONDecodeError:
            return None

        business_chat = data.get("telegram_business_chat")
        if not isinstance(business_chat, dict):
            return None
        if not business_chat.get("business_connection_id") or not business_chat.get("chat_id"):
            return None
        return business_chat


telegram_delivery_service = TelegramDeliveryService()
