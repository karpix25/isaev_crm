"""Deliver finished estimate files to leads."""

from __future__ import annotations

import uuid
from pathlib import Path

from aiogram.types import FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead
from src.services.user_bot_service import user_bot_service


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

        from src.bot import bot

        if not bot:
            raise ValueError("telegram_bot_unavailable")

        sent = await bot.send_document(
            chat_id=int(lead.telegram_id),
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


estimate_delivery_service = EstimateDeliveryService()
