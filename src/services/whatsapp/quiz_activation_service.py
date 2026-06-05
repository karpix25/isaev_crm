from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ChatMessage, Lead, MessageStatus, MessageTransport
from src.services.chat_service import chat_service
from src.services.whatsapp.transport_service import WhatsAppTransportError, whatsapp_transport_service

logger = logging.getLogger(__name__)


QUIZ_FIELD_LABELS = {
    "type": "Объект",
    "area": "Площадь",
    "rtype": "Тип ремонта",
    "state": "Состояние",
    "rooms": "Объем",
    "design": "Дизайн",
    "deadline": "Срок",
    "budget": "Бюджет",
}

QUIZ_VALUE_LABELS = {
    "type": {"flat": "Квартира", "house": "Дом", "commercial": "Коммерция"},
    "area": {"xs": "до 40 м²", "sm": "40-70 м²", "md": "70-100 м²", "lg": "100+ м²"},
    "rtype": {"cosm": "Косметический", "finish": "Чистовая отделка", "full": "Под ключ"},
    "state": {"rough": "Черновая отделка", "lived": "Жилое, требует обновления", "demo": "Нужен полный снос"},
    "rooms": {"partial": "Только санузел / кухня", "several": "Несколько комнат", "all": "Вся квартира целиком"},
    "design": {"yes": "Да, уже готов", "wip": "В процессе разработки", "no": "Нет, хочу в подарок"},
    "deadline": {"asap": "Как можно скорее", "soon": "В течение 1-3 месяцев", "later": "Не спешу"},
    "budget": {"b1": "До 1 млн ₽", "b2": "1-2 млн ₽", "b3": "2-4 млн ₽", "b4": "От 4 млн ₽"},
}


class WhatsAppQuizActivationService:
    async def send_activation_reply(
        self,
        db: AsyncSession,
        lead: Lead,
        *,
        chat_id: str,
        session_token: str,
        source: str,
    ) -> bool:
        if not whatsapp_transport_service.is_configured():
            logger.warning("WhatsApp activation skipped: transport is not configured")
            return False

        if not await self._estimate_already_sent(db, lead.id, session_token):
            estimate_text = self._build_estimate_text(lead)
            if estimate_text:
                return await self._send_and_store(
                    db=db,
                    lead=lead,
                    chat_id=chat_id,
                    text=estimate_text,
                    metadata={
                        "source": source,
                        "engine": "bot_template",
                        "type": "quiz_estimate_after_activation",
                        "session_token": session_token,
                    },
                )

        welcome_text = await self._build_welcome_text(db, lead)
        return await self._send_and_store(
            db=db,
            lead=lead,
            chat_id=chat_id,
            text=welcome_text,
            metadata={"source": source, "engine": "bot_template", "type": "quiz_whatsapp_activation"},
        )

    async def _send_and_store(
        self,
        db: AsyncSession,
        lead: Lead,
        *,
        chat_id: str,
        text: str,
        metadata: dict[str, Any],
    ) -> bool:
        try:
            result = await whatsapp_transport_service.send_text(chat_id=chat_id, text=text)
        except WhatsAppTransportError:
            logger.warning("Failed to send WhatsApp quiz activation reply for lead %s", lead.id, exc_info=True)
            return False

        message = await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            sender_name="Bot",
            ai_metadata={
                **metadata,
                "provider": result.provider,
                "external_message_id": result.message_id,
                "external_chat_id": result.chat_id,
            },
            status=MessageStatus.SENT,
            transport=MessageTransport.WHATSAPP,
        )
        if hasattr(message, "external_provider"):
            message.external_provider = result.provider
        if hasattr(message, "external_message_id"):
            message.external_message_id = result.message_id
        if hasattr(message, "external_chat_id"):
            message.external_chat_id = result.chat_id
        await db.commit()
        return True

    async def _estimate_already_sent(self, db: AsyncSession, lead_id, session_token: str) -> bool:
        result = await db.execute(select(ChatMessage).where(ChatMessage.lead_id == lead_id))
        for message in result.scalars().all():
            metadata = message.ai_metadata if isinstance(message.ai_metadata, dict) else {}
            if (
                metadata.get("type") == "quiz_estimate_after_activation"
                and metadata.get("session_token") == session_token
            ):
                return True
        return False

    async def _build_welcome_text(self, db: AsyncSession, lead: Lead) -> str:
        try:
            from src.services.lead_stage_context_service import lead_stage_context_service

            stage_context = await lead_stage_context_service.build_context(db=db, lead=lead)
            next_action = stage_context.metadata.get("next_action")
        except Exception:
            logger.warning("Failed to build WhatsApp quiz activation stage context for lead %s", lead.id, exc_info=True)
            next_action = None

        if next_action == "awaiting_design_project":
            return (
                "Здравствуйте! Я Александр, менеджер компании ISAEV GROUP.\n\n"
                "Следующий шаг — пришлите сюда дизайн-проект файлом. Мы проверим объемы, чертежи и спорные места, "
                "чтобы точнее рассчитать работы без стройматериалов."
            )
        if next_action == "awaiting_measurement_slot":
            return (
                "Здравствуйте! Я Александр, менеджер компании ISAEV GROUP.\n\n"
                f"{self._measurement_cta()}"
            )
        if next_action == "confirm_measurement":
            return (
                "Здравствуйте! Я Александр, менеджер компании ISAEV GROUP.\n\n"
                "Вижу, что вы уже выбрали данные для замера.\n"
                "Если нужно изменить дату, адрес или телефон — напишите сюда."
            )
        return (
            "Здравствуйте! Я Александр, менеджер компании ISAEV GROUP.\n\n"
            "Вижу вашу заявку по квизу.\n\n"
            "Напишите сюда любой вопрос — продолжим по вашим данным и подскажем понятный следующий шаг."
        )

    def _build_estimate_text(self, lead: Lead) -> str:
        data = self._parse_data(lead.extracted_data)
        quiz = data.get("quiz") if isinstance(data.get("quiz"), dict) else {}
        price = quiz.get("price") if isinstance(quiz.get("price"), dict) else {}
        price_label = str(price.get("label") or "").strip()
        if not price_label:
            return ""

        lines = [
            "Здравствуйте! Я Александр, менеджер компании ISAEV GROUP.",
            "",
            "Предварительная цена по работам без стройматериалов:",
            price_label,
        ]
        summary = self._quiz_summary_lines(quiz)
        if summary:
            lines.extend(["", "Данные из квиза:", *summary])
        lines.extend(["", self._measurement_cta()])
        return "\n".join(lines)

    def _measurement_cta(self) -> str:
        return (
            "Чтобы цена была точнее, лучше начать с бесплатного осмотра. "
            "Инженер посмотрит объект, замерит объемы и проверит нюансы, которые не видно по квизу.\n\n"
            "Напишите, пожалуйста, удобный день и время. Подберу ближайшее окно и подтвержу запись."
        )

    def _quiz_summary_lines(self, quiz: dict[str, Any]) -> list[str]:
        answers = quiz.get("answers") if isinstance(quiz.get("answers"), dict) else {}
        lines: list[str] = []
        for key, label in QUIZ_FIELD_LABELS.items():
            value = str(answers.get(key) or "").strip()
            if value:
                lines.append(f"{label}: {QUIZ_VALUE_LABELS.get(key, {}).get(value, value)}")
        return lines

    def _parse_data(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


whatsapp_quiz_activation_service = WhatsAppQuizActivationService()
