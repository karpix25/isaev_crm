from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead, User
from src.models.user import UserRole
from src.services.telegram_notification_service import telegram_notification_service

logger = logging.getLogger(__name__)


class LeadManagerNotificationService:
    HOT_LEAD_KEY = "hot_lead"
    MEASUREMENT_KEY = "measurement_booking"
    ESTIMATE_REQUEST_KEY = "estimate_request"

    async def notify_hot_lead_if_needed(
        self,
        db: AsyncSession,
        lead: Lead | None,
        *,
        reason: str,
        source: str,
        extracted_data: dict[str, Any] | None = None,
    ) -> bool:
        if not lead:
            return False
        if not telegram_notification_service.has_recipients("hot_lead"):
            logger.warning("Skipping hot lead notification: no recipients lead_id=%s", lead.id)
            return False

        data = self._parse_extracted_data(lead.extracted_data)
        if extracted_data:
            ai_data = data.get("ai_extracted") if isinstance(data.get("ai_extracted"), dict) else {}
            data["ai_extracted"] = {**ai_data, **extracted_data}

        notifications = self._notifications(data)
        notice_key = self._hot_lead_notice_key(source)
        hot_lead_notice = notifications.get(notice_key)
        if isinstance(hot_lead_notice, dict) and hot_lead_notice.get("sent_at"):
            logger.info("Hot lead notification already sent: lead_id=%s source=%s", lead.id, source)
            return False

        sent = await telegram_notification_service.send_to_managers(
            self._build_hot_lead_text(lead=lead, data=data, reason=reason),
            topic="hot_lead",
        )
        if not sent:
            logger.warning("Hot lead notification was not delivered: lead_id=%s source=%s", lead.id, source)
            return False

        notifications[notice_key] = {
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "reason": reason,
        }
        data["manager_notifications"] = notifications
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        await db.commit()
        await db.refresh(lead)
        return True

    async def notify_measurement_booking_if_needed(
        self,
        db: AsyncSession,
        lead: Lead | None,
        *,
        start: str,
        address: str,
        status: str,
        booking_uid: str | None,
        source: str,
    ) -> bool:
        if not lead:
            return False
        if not telegram_notification_service.has_recipients("measurement"):
            logger.warning("Skipping measurement notification: no recipients lead_id=%s", lead.id)
            return False

        data = self._parse_extracted_data(lead.extracted_data)
        notifications = self._notifications(data)
        notice_key = self._measurement_notice_key(start=start, address=address, booking_uid=booking_uid)
        measurement_notice = notifications.get(notice_key)
        if isinstance(measurement_notice, dict) and measurement_notice.get("sent_at"):
            logger.info("Measurement notification already sent: lead_id=%s key=%s", lead.id, notice_key)
            return False

        sent = await telegram_notification_service.send_to_managers(
            self._build_measurement_text(
                lead=lead,
                start=start,
                address=address,
                status=status,
                booking_uid=booking_uid,
            ),
            topic="measurement",
        )
        if not sent:
            logger.warning("Measurement notification was not delivered: lead_id=%s source=%s", lead.id, source)
            return False

        notifications[notice_key] = {
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "status": status,
            "booking_uid": booking_uid,
        }
        data["manager_notifications"] = notifications
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        await db.commit()
        await db.refresh(lead)
        return True

    async def notify_estimate_request_if_needed(
        self,
        db: AsyncSession,
        lead: Lead | None,
        *,
        file_record: dict[str, Any],
    ) -> bool:
        if not lead:
            return False

        manager_recipients = telegram_notification_service.recipients_for("estimate_request")
        estimator_chat_ids = await self._estimator_chat_ids(db, lead)
        if not manager_recipients and not estimator_chat_ids:
            logger.warning("No estimator Telegram recipients found for lead %s", lead.id)
            return False

        data = self._parse_extracted_data(lead.extracted_data)
        notifications = self._notifications(data)
        notice_key = self._estimate_notice_key(file_record)
        estimate_notice = notifications.get(notice_key)
        if isinstance(estimate_notice, dict) and estimate_notice.get("sent_at"):
            logger.info("Estimate request notification already sent: lead_id=%s key=%s", lead.id, notice_key)
            return False

        text = self._build_estimate_request_text(lead=lead, file_record=file_record)
        sent = await telegram_notification_service.send_to_managers(text, topic="estimate_request")

        plain_topic_chat_ids = {
            recipient.chat_id
            for recipient in manager_recipients
            if recipient.message_thread_id is None
        }
        sent += await self._send_to_estimator_chat_ids(
            text=text,
            chat_ids=estimator_chat_ids,
            excluded_chat_ids=plain_topic_chat_ids,
            lead=lead,
        )
        if not sent:
            logger.warning("Estimate request notification was not delivered: lead_id=%s", lead.id)
            return False

        notifications[notice_key] = {
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "filename": file_record.get("filename"),
            "url": file_record.get("url"),
        }
        data["manager_notifications"] = notifications
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        await db.commit()
        await db.refresh(lead)
        return True

    def _build_hot_lead_text(self, *, lead: Lead, data: dict[str, Any], reason: str) -> str:
        quiz = data.get("quiz") if isinstance(data.get("quiz"), dict) else {}
        answers = quiz.get("answers") if isinstance(quiz.get("answers"), dict) else {}
        price = quiz.get("price") if isinstance(quiz.get("price"), dict) else {}
        measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}

        lines = [
            "🔥 Горячий лид",
            "",
            f"Причина: {reason}",
            f"Клиент: {lead.full_name or 'Клиент квиза'}",
            f"Телефон: {lead.phone or 'не указан'}",
        ]
        if lead.username or lead.telegram_id:
            lines.append(f"Telegram: @{lead.username}" if lead.username else f"Telegram ID: {lead.telegram_id}")

        summary_lines = [
            ("Объект", self._pick(answers, "object_type", "object", "property_type")),
            ("Площадь", self._pick(answers, "area", "area_sqm", "square")),
            ("Ремонт", self._pick(answers, "repair_type", "repair", "finish_type")),
            ("Дизайн", self._pick(answers, "design", "design_project")),
            ("Бюджет", self._pick(answers, "budget", "budget_range")),
            ("Цена", price.get("label")),
            ("Замер", self._format_measurement(measurement)),
        ]
        present_summary = [f"{label}: {value}" for label, value in summary_lines if value]
        if present_summary:
            lines.extend(["", *present_summary])

        lines.extend(["", f"Лид: {lead.id}"])
        return "\n".join(lines)

    def _pick(self, data: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = data.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    def _format_measurement(self, measurement: dict[str, Any]) -> str:
        start = str(measurement.get("start") or "").strip()
        address = str(measurement.get("address") or "").strip()
        if start and address:
            return f"{start}, {address}"
        return start or address

    def _build_measurement_text(
        self,
        *,
        lead: Lead,
        start: str,
        address: str,
        status: str,
        booking_uid: str | None,
    ) -> str:
        status_label = "✅ Замер записан в календарь" if status == "booked" else "🟡 Клиент выбрал слот замера"
        lines = [
            status_label,
            "",
            f"👤 Клиент: {lead.full_name or 'Клиент квиза'}",
            f"📞 Телефон: {lead.phone or 'не указан'}",
            f"📅 Дата: {start}",
            f"📍 Адрес: {address}",
            f"🆔 Лид: {lead.id}",
        ]
        if booking_uid:
            lines.append(f"🔖 Booking: {booking_uid}")
        return "\n".join(lines)

    def _build_estimate_request_text(self, *, lead: Lead, file_record: dict[str, Any]) -> str:
        return "\n".join(
            [
                "📐 Нужен просчет сметы",
                "",
                f"👤 Клиент: {lead.full_name or 'Не указан'}",
                f"📞 Телефон: {lead.phone or 'не указан'}",
                f"📎 Файл: {file_record.get('filename') or file_record.get('url')}",
                f"🔗 Ссылка: {file_record.get('url')}",
                "⏱ Обычный срок подготовки: до 24 часов",
                f"🆔 Лид: {lead.id}",
            ]
        )

    def _notifications(self, data: dict[str, Any]) -> dict[str, Any]:
        notifications = data.get("manager_notifications")
        return notifications if isinstance(notifications, dict) else {}

    def _hot_lead_notice_key(self, source: str) -> str:
        if "measurement" in source:
            return "hot_lead_measurement"
        return self.HOT_LEAD_KEY

    def _measurement_notice_key(self, *, start: str, address: str, booking_uid: str | None) -> str:
        stable_id = booking_uid or f"{start}:{address}"
        return f"{self.MEASUREMENT_KEY}:{stable_id}"

    def _estimate_notice_key(self, file_record: dict[str, Any]) -> str:
        stable_id = str(file_record.get("url") or file_record.get("uploaded_at") or file_record.get("filename") or "")
        return f"{self.ESTIMATE_REQUEST_KEY}:{stable_id}"

    async def _estimator_chat_ids(self, db: AsyncSession, lead: Lead) -> list[int]:
        ids: set[int] = set()
        result = await db.execute(
            select(User.telegram_id).where(
                User.org_id == lead.org_id,
                User.telegram_id.is_not(None),
                User.role.in_([UserRole.ADMIN, UserRole.MANAGER, UserRole.WORKER]),
            )
        )
        for telegram_id in result.scalars().all():
            if telegram_id:
                ids.add(int(telegram_id))
        return sorted(ids)

    async def _send_to_estimator_chat_ids(
        self,
        *,
        text: str,
        chat_ids: list[int],
        excluded_chat_ids: set[int],
        lead: Lead,
    ) -> int:
        if not chat_ids:
            return 0
        try:
            from src.bot import bot
        except Exception:
            bot = None
        if not bot:
            logger.warning("Telegram bot is not available for estimate notification")
            return 0

        sent = 0
        for chat_id in chat_ids:
            if chat_id in excluded_chat_ids:
                continue
            try:
                await bot.send_message(chat_id=chat_id, text=text)
                sent += 1
            except Exception:
                logger.warning("Failed to notify estimator %s for lead %s", chat_id, lead.id, exc_info=True)
        return sent

    def _parse_extracted_data(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


lead_manager_notification_service = LeadManagerNotificationService()
