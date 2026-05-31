"""Register client files that require estimate preparation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead, User
from src.models.lead import LeadStatus
from src.models.user import UserRole


logger = logging.getLogger(__name__)


class EstimateRequestService:
    async def register_file(
        self,
        db: AsyncSession,
        lead: Lead,
        *,
        url: str,
        filename: str | None = None,
        source: str,
        telegram_file_id: str | None = None,
    ) -> dict[str, Any]:
        data = self._parse_extracted_data(lead.extracted_data)
        file_record = {
            "url": url,
            "filename": filename or "Файл для расчета",
            "source": source,
            "telegram_file_id": telegram_file_id,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "sla_hours": 24,
        }

        estimate_request = data.get("estimate_request")
        if not isinstance(estimate_request, dict):
            estimate_request = {}
        files = estimate_request.get("files") if isinstance(estimate_request.get("files"), list) else []
        files.append(file_record)
        estimate_request.update(
            {
                "status": "needs_estimate",
                "sla_hours": 24,
                "requested_at": file_record["uploaded_at"],
                "latest_file": file_record,
                "files": files,
            }
        )
        data["estimate_request"] = estimate_request

        quiz = data.get("quiz") if isinstance(data.get("quiz"), dict) else {}
        quiz["design_project_file_url"] = url
        if filename:
            quiz["design_project_filename"] = filename
        quiz["updated_at"] = file_record["uploaded_at"]
        data["quiz"] = quiz

        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        lead.status = LeadStatus.ESTIMATE_PREPARING.value
        await db.commit()
        await db.refresh(lead)

        await self.notify_estimators(db=db, lead=lead, file_record=file_record)
        return file_record

    async def notify_estimators(self, db: AsyncSession, lead: Lead, file_record: dict[str, Any]) -> None:
        recipient_ids = await self._estimator_chat_ids(db, lead)
        if not recipient_ids:
            logger.warning("No estimator Telegram recipients found for lead %s", lead.id)
            return

        try:
            from src.bot import bot
        except Exception:
            bot = None
        if not bot:
            logger.warning("Telegram bot is not available for estimate notification")
            return

        text = (
            "📐 Нужен просчет сметы\n\n"
            f"👤 Клиент: {lead.full_name or 'Не указан'}\n"
            f"📞 Телефон: {lead.phone or 'не указан'}\n"
            f"📎 Файл: {file_record.get('filename') or file_record.get('url')}\n"
            f"🔗 Ссылка: {file_record.get('url')}\n"
            "⏱ Обычный срок подготовки: до 24 часов\n"
            f"🆔 Лид: {lead.id}"
        )
        for chat_id in recipient_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=text)
            except Exception:
                logger.warning("Failed to notify estimator %s for lead %s", chat_id, lead.id, exc_info=True)

    async def _estimator_chat_ids(self, db: AsyncSession, lead: Lead) -> list[int]:
        ids: set[int] = set()
        try:
            from src.config import settings

            manager_id = getattr(settings, "manager_telegram_id", None)
            if manager_id:
                ids.add(int(manager_id))
        except Exception:
            pass

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

    def _parse_extracted_data(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


estimate_request_service = EstimateRequestService()
