"""Deliver finished estimate files to leads."""

from __future__ import annotations

import json
import uuid
from typing import Any
from pathlib import Path

from aiogram.types import FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead
from src.services.user_bot_service import user_bot_service
from src.services.whatsapp.media import media_type_from_mimetype, mimetype_for, public_media_url
from src.services.whatsapp.transport_service import WhatsAppTransportError, whatsapp_transport_service


class EstimateDeliveryService:
    async def send_telegram_document(
        self,
        db: AsyncSession,
        lead: Lead,
        *,
        text: str,
        file_path: Path,
    ) -> int | None:
        if not lead.telegram_id:
            raise ValueError("lead_has_no_telegram")

        business_chat = self._business_chat_data(lead)
        if business_chat:
            return await self._send_business_bot_file(
                text=text,
                file_path=file_path,
                business_chat=business_chat,
            )

        if lead.source in {"userbot", "CRM"}:
            await self._send_userbot_file(
                db=db,
                org_id=lead.org_id,
                telegram_id=int(lead.telegram_id),
                file_path=file_path,
                caption=text,
                username=lead.username,
            )
            return None

        return await self._send_official_bot_file(
            telegram_id=int(lead.telegram_id),
            text=text,
            file_path=file_path,
        )

    async def send_whatsapp_document(
        self,
        lead: Lead,
        *,
        text: str,
        media_url: str,
        filename: str | None = None,
    ) -> str | None:
        if not lead.phone:
            raise ValueError("lead_has_no_whatsapp")
        public_url = public_media_url(media_url)
        if not public_url:
            raise ValueError("whatsapp_public_media_url_missing")
        if not whatsapp_transport_service.is_configured():
            raise ValueError("whatsapp_transport_unavailable")

        mimetype = mimetype_for(filename)
        try:
            result = await whatsapp_transport_service.send_media(
                chat_id=lead.phone,
                media_url=public_url,
                mediatype=media_type_from_mimetype(mimetype, filename),
                mimetype=mimetype,
                filename=filename,
                caption=text,
            )
        except WhatsAppTransportError as exc:
            raise ValueError(f"whatsapp_send_failed:{exc}") from exc
        return result.message_id

    async def _send_business_bot_file(
        self,
        *,
        text: str,
        file_path: Path,
        business_chat: dict[str, Any],
    ) -> int:
        from src.bot import bot

        if not bot:
            raise ValueError("telegram_bot_unavailable")

        sent = await bot.send_document(
            chat_id=int(business_chat["chat_id"]),
            document=FSInputFile(file_path),
            caption=text,
            business_connection_id=str(business_chat["business_connection_id"]),
        )
        return sent.message_id

    async def _send_official_bot_file(self, *, telegram_id: int, text: str, file_path: Path) -> int:
        from src.bot import bot

        if not bot:
            raise ValueError("telegram_bot_unavailable")

        sent = await bot.send_document(
            chat_id=telegram_id,
            document=FSInputFile(file_path),
            caption=text,
        )
        return sent.message_id

    async def _send_userbot_file(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        telegram_id: int,
        *,
        file_path: Path,
        caption: str,
        username: str | None = None,
    ) -> None:
        client = await self._get_userbot_client(db, org_id)
        try:
            await client.send_file(telegram_id, file=str(file_path), caption=caption)
        except ValueError as exc:
            if "Could not find the input entity" in str(exc) and username:
                await client.send_file(username, file=str(file_path), caption=caption)
                return
            raise

    async def _get_userbot_client(self, db: AsyncSession, org_id: uuid.UUID):
        client = user_bot_service.clients.get(org_id)
        if client:
            return client

        bot_record = await user_bot_service._get_or_create_bot_record(db, org_id)
        if not bot_record.is_authorized or not bot_record.session_string:
            raise ValueError("userbot_unavailable")

        from telethon import TelegramClient, sessions

        client = TelegramClient(
            sessions.StringSession(bot_record.session_string),
            bot_record.api_id,
            bot_record.api_hash,
        )
        await client.connect()
        if not await client.is_user_authorized():
            raise ValueError("userbot_unavailable")
        user_bot_service.clients[org_id] = client
        return client

    def _business_chat_data(self, lead: Lead) -> dict[str, Any] | None:
        data = self._parse_data(lead.extracted_data)
        business_chat = data.get("telegram_business_chat")
        if not isinstance(business_chat, dict):
            return None
        if not business_chat.get("business_connection_id") or not business_chat.get("chat_id"):
            return None
        return business_chat

    def _parse_data(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


estimate_delivery_service = EstimateDeliveryService()
