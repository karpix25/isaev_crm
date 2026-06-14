from __future__ import annotations

from datetime import datetime, timezone

from aiogram.types import Message
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.utils import get_default_org_id
from src.database import AsyncSessionLocal
from src.models import ChatMessage, Lead, MessageDirection, MessageStatus, MessageTransport
from src.services.chat_service import chat_service


class TelegramBusinessAuthorMessageService:
    async def save_text_message(self, message: Message) -> bool:
        text = (message.text or "").strip()
        if not text:
            return False

        business_connection_id = getattr(message, "business_connection_id", None)
        chat_id = getattr(getattr(message, "chat", None), "id", None)
        author_id = getattr(getattr(message, "from_user", None), "id", None)
        if not business_connection_id or not chat_id or not author_id:
            return False

        async with AsyncSessionLocal() as db:
            lead = await self._find_lead(db, int(chat_id))
            if not lead:
                return False

            message_id = getattr(message, "message_id", None)
            if message_id and await self._message_exists(db, lead, int(message_id)):
                return True

            await chat_service.send_outbound_message(
                db=db,
                lead_id=lead.id,
                content=text,
                telegram_message_id=message_id,
                sender_name=getattr(message.from_user, "full_name", None) or "Manager",
                ai_metadata={
                    "source": "telegram_business_author",
                    "business_connection_id": business_connection_id,
                    "business_chat_id": chat_id,
                    "author_telegram_id": author_id,
                    "author_username": getattr(message.from_user, "username", None),
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                },
                status=MessageStatus.SENT,
                transport=MessageTransport.TELEGRAM,
            )
            return True

    async def _find_lead(self, db: AsyncSession, chat_id: int) -> Lead | None:
        org_id = await get_default_org_id(db)
        ordering = (Lead.last_message_at.desc().nullslast(), Lead.created_at.desc())
        result = await db.execute(
            select(Lead)
            .where(Lead.org_id == org_id, Lead.telegram_id == chat_id)
            .order_by(*ordering)
            .limit(1)
        )
        lead = result.scalar_one_or_none()
        if lead:
            return lead

        chat_id_text = str(chat_id)
        result = await db.execute(
            select(Lead)
            .where(
                Lead.org_id == org_id,
                Lead.extracted_data.isnot(None),
                or_(
                    Lead.extracted_data.contains(f'"chat_id": {chat_id_text}'),
                    Lead.extracted_data.contains(f'"chat_id":"{chat_id_text}"'),
                    Lead.extracted_data.contains(f'"chat_id": "{chat_id_text}"'),
                ),
            )
            .order_by(*ordering)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _message_exists(self, db: AsyncSession, lead: Lead, message_id: int) -> bool:
        result = await db.execute(
            select(ChatMessage.id)
            .where(
                ChatMessage.lead_id == lead.id,
                ChatMessage.direction == MessageDirection.OUTBOUND,
                ChatMessage.telegram_message_id == message_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None


telegram_business_author_message_service = TelegramBusinessAuthorMessageService()
