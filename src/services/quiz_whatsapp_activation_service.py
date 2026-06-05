from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead

logger = logging.getLogger(__name__)


class QuizWhatsAppActivationService:
    async def maybe_send_after_quiz(
        self,
        db: AsyncSession,
        lead: Lead,
        *,
        session_token: str,
        preferred_messenger: str | None,
        source: str,
    ) -> bool:
        if (preferred_messenger or "").strip().lower() != "whatsapp":
            return False

        chat_id = (lead.phone or "").strip()
        if not chat_id:
            logger.info("WhatsApp quiz activation skipped for lead %s: no phone", lead.id)
            return False

        try:
            from src.services.whatsapp.quiz_activation_service import whatsapp_quiz_activation_service

            return await whatsapp_quiz_activation_service.send_activation_reply(
                db=db,
                lead=lead,
                chat_id=chat_id,
                session_token=session_token,
                source=source,
            )
        except Exception:
            logger.warning("Failed to send WhatsApp quiz activation for lead %s", lead.id, exc_info=True)
            return False


quiz_whatsapp_activation_service = QuizWhatsAppActivationService()
