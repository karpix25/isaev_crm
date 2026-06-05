from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.utils import get_default_org_id
from src.models import ChatMessage, Lead, LeadStatus, MessageDirection, MessageTransport
from src.services.analytics_service import analytics_service
from src.services.chat_service import chat_service
from src.services.estimate_request_service import estimate_request_service
from src.services.lead_audit_service import lead_audit_service
from src.services.quiz_service import quiz_service
from src.services.whatsapp.phone import normalize_phone, normalize_phone_digits
from src.services.whatsapp.types import WhatsAppIncomingMessage
from src.services.whatsapp.media_storage import whatsapp_media_storage

logger = logging.getLogger(__name__)


class WhatsAppInboundMessageService:
    async def process_messages(
        self,
        db: AsyncSession,
        messages: list[WhatsAppIncomingMessage],
    ) -> int:
        if not messages:
            return 0

        org_id = await get_default_org_id(db)
        saved = 0
        for item in messages:
            lead = await quiz_service.link_whatsapp_message(
                db=db,
                org_id=org_id,
                text=item.text,
                chat_id=item.chat_id,
                sender_name=item.sender_name,
            )
            linked_by_quiz = lead is not None
            if not lead:
                lead = await self._get_or_create_lead(
                    db=db,
                    org_id=org_id,
                    chat_id=item.chat_id,
                    sender_name=item.sender_name,
                )

            if await self._message_exists(db, lead.id, item):
                continue

            media_url = self._media_url(item)
            metadata = {
                "source": item.provider,
                "channel": "whatsapp",
                "provider": item.provider,
                "instance": item.instance,
                "external_message_id": item.message_id,
                "external_chat_id": item.chat_id,
            }
            if item.attachment:
                metadata["attachment"] = {
                    "url": item.attachment.url,
                    "filename": item.attachment.filename,
                    "mimetype": item.attachment.mimetype,
                    "size": item.attachment.size,
                    "has_base64": bool(item.attachment.data_base64),
                }

            message = await chat_service.save_incoming_message(
                db=db,
                lead_id=lead.id,
                content=item.text or self._attachment_content(item),
                media_url=media_url,
                sender_name=item.sender_name or "WhatsApp",
                ai_metadata=metadata,
                transport=MessageTransport.WHATSAPP,
            )
            self._apply_external_fields(message, item)
            if item.attachment:
                self._apply_media_fields(message, item)
            await db.commit()

            if not linked_by_quiz:
                await self._record_generic_inbound_event(db, lead, item)
                await self._apply_inbound_stage(db, lead, item)
            await self._register_estimate_attachment(db, lead, item, media_url)
            saved += 1
        return saved

    async def _get_or_create_lead(self, db: AsyncSession, org_id, chat_id: str, sender_name: str | None) -> Lead:
        lead = await self.find_lead_by_chat_id(db, org_id=org_id, chat_id=chat_id)
        if lead:
            self._mark_whatsapp_presence(lead, chat_id)
            await db.commit()
            return lead

        normalized_phone = normalize_phone(chat_id)
        data = {
            "messengers": {"whatsapp": True},
            "whatsapp_wa_id": normalize_phone_digits(chat_id),
            "whatsapp_chat": {
                "chat_id": chat_id,
                "linked_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        lead = Lead(
            org_id=org_id,
            full_name=(sender_name or "").strip() or None,
            phone=normalized_phone,
            status=LeadStatus.NEW.value,
            source="whatsapp",
            extracted_data=json.dumps(data, ensure_ascii=False),
            telegram_lookup_status="not_checked",
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        return lead

    async def find_lead_by_chat_id(self, db: AsyncSession, org_id, chat_id: str) -> Lead | None:
        digits = normalize_phone_digits(chat_id)
        if not digits:
            return None

        tail10 = digits[-10:]
        result = await db.execute(
            select(Lead)
            .where(
                and_(
                    Lead.org_id == org_id,
                    Lead.phone.is_not(None),
                    or_(Lead.phone.ilike(f"%{digits}%"), Lead.phone.ilike(f"%{tail10}%")),
                )
            )
            .order_by(desc(Lead.updated_at))
            .limit(50)
        )
        for lead in result.scalars().all():
            lead_digits = normalize_phone_digits(lead.phone)
            if lead_digits and (lead_digits == digits or lead_digits.endswith(tail10)):
                return lead
        return None

    async def _message_exists(self, db: AsyncSession, lead_id, item: WhatsAppIncomingMessage) -> bool:
        if not item.message_id:
            return False

        query = (
            select(ChatMessage)
            .where(
                ChatMessage.lead_id == lead_id,
                ChatMessage.transport == MessageTransport.WHATSAPP,
                ChatMessage.direction == MessageDirection.INBOUND,
            )
            .order_by(desc(ChatMessage.created_at))
            .limit(200)
        )
        result = await db.execute(query)
        for message in result.scalars().all():
            external_id = getattr(message, "external_message_id", None)
            provider = getattr(message, "external_provider", None)
            if external_id and str(external_id) == str(item.message_id):
                if not provider or str(provider) == item.provider:
                    return True
            metadata = message.ai_metadata or {}
            if str(metadata.get("external_message_id") or metadata.get("wazzup_message_id") or "") == str(item.message_id):
                return True
        return False

    async def _record_generic_inbound_event(self, db: AsyncSession, lead: Lead, item: WhatsAppIncomingMessage) -> None:
        data = self._parse_data(lead.extracted_data)
        token = data.get("quiz_session_token")
        if not token:
            return
        try:
            await analytics_service.record_event(
                db=db,
                session_token=str(token),
                event_type="whatsapp_message_received",
                step_id="messenger",
                event_data={"lead_id": str(lead.id), "chat_id": item.chat_id, "provider": item.provider},
            )
        except Exception:
            logger.warning("Failed to record generic WhatsApp inbound event for lead %s", lead.id, exc_info=True)

    async def _apply_inbound_stage(self, db: AsyncSession, lead: Lead, item: WhatsAppIncomingMessage) -> None:
        if lead.status not in {
            LeadStatus.NEW.value,
            LeadStatus.QUIZ_COMPLETED.value,
            LeadStatus.MESSENGER_PENDING.value,
        }:
            return

        previous = lead.status
        lead.status = LeadStatus.CONSULTING.value
        await lead_audit_service.log_change(
            db=db,
            lead=lead,
            action="stage_auto_updated",
            source=f"{item.provider}_webhook",
            changes={
                "status": {"old": previous, "new": LeadStatus.CONSULTING.value},
                "reason": {"old": None, "new": "whatsapp_message_received"},
            },
        )
        await db.commit()

    def _mark_whatsapp_presence(self, lead: Lead, chat_id: str) -> None:
        data = self._parse_data(lead.extracted_data)
        data.setdefault("messengers", {})["whatsapp"] = True
        data["whatsapp_wa_id"] = normalize_phone_digits(chat_id)
        data["whatsapp_chat"] = {
            **(data.get("whatsapp_chat") if isinstance(data.get("whatsapp_chat"), dict) else {}),
            "chat_id": chat_id,
            "linked_at": datetime.now(timezone.utc).isoformat(),
        }
        lead.extracted_data = json.dumps(data, ensure_ascii=False)

    def _apply_external_fields(self, message: ChatMessage, item: WhatsAppIncomingMessage) -> None:
        if hasattr(message, "external_provider"):
            message.external_provider = item.provider
        if hasattr(message, "external_message_id"):
            message.external_message_id = item.message_id
        if hasattr(message, "external_chat_id"):
            message.external_chat_id = item.chat_id

    def _apply_media_fields(self, message: ChatMessage, item: WhatsAppIncomingMessage) -> None:
        if not item.attachment:
            return
        if hasattr(message, "media_filename"):
            message.media_filename = item.attachment.filename
        if hasattr(message, "media_mimetype"):
            message.media_mimetype = item.attachment.mimetype
        if hasattr(message, "media_size"):
            message.media_size = item.attachment.size

    def _media_url(self, item: WhatsAppIncomingMessage) -> str | None:
        if not item.attachment:
            return None
        saved_url = whatsapp_media_storage.save_base64_attachment(item.attachment)
        return saved_url or item.attachment.url

    async def _register_estimate_attachment(
        self,
        db: AsyncSession,
        lead: Lead,
        item: WhatsAppIncomingMessage,
        media_url: str | None,
    ) -> None:
        if not item.attachment or not media_url:
            return
        mimetype = (item.attachment.mimetype or "").lower()
        if mimetype.startswith("audio/"):
            return
        try:
            await estimate_request_service.register_file(
                db=db,
                lead=lead,
                url=media_url,
                filename=item.attachment.filename or "WhatsApp файл",
                source=f"{item.provider}_whatsapp_attachment",
            )
        except Exception:
            logger.warning("Failed to register WhatsApp attachment for estimate: lead=%s", lead.id, exc_info=True)

    def _attachment_content(self, item: WhatsAppIncomingMessage) -> str:
        if not item.attachment:
            return "[WhatsApp message]"
        return f"[WhatsApp файл] {item.attachment.filename or item.attachment.mimetype or 'вложение'}"

    def _parse_data(self, value: str | None) -> dict:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


whatsapp_inbound_message_service = WhatsAppInboundMessageService()
