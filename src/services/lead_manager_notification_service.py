from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead
from src.services.telegram_notification_service import telegram_notification_service

logger = logging.getLogger(__name__)


class LeadManagerNotificationService:
    HOT_LEAD_KEY = "hot_lead"

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

        notifications = data.get("manager_notifications")
        if not isinstance(notifications, dict):
            notifications = {}
        hot_lead_notice = notifications.get(self.HOT_LEAD_KEY)
        if isinstance(hot_lead_notice, dict) and hot_lead_notice.get("sent_at"):
            return False

        sent = await telegram_notification_service.send_to_managers(
            self._build_hot_lead_text(lead=lead, data=data, reason=reason),
            topic="hot_lead",
        )
        if not sent:
            logger.warning("Hot lead notification was not delivered: lead_id=%s source=%s", lead.id, source)
            return False

        notifications[self.HOT_LEAD_KEY] = {
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "reason": reason,
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

    def _parse_extracted_data(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


lead_manager_notification_service = LeadManagerNotificationService()
