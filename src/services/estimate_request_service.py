"""Register client files that require estimate preparation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead, MessageStatus, MessageTransport, User
from src.models.lead import LeadStatus
from src.models.user import UserRole
from src.services.chat_service import chat_service
from src.services.media_path_service import media_path_service


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

    async def register_final_file(
        self,
        db: AsyncSession,
        lead: Lead,
        *,
        url: str,
        filename: str | None = None,
    ) -> dict[str, Any]:
        data = self._parse_extracted_data(lead.extracted_data)
        uploaded_at = datetime.now(timezone.utc).isoformat()
        file_record = {
            "url": url,
            "filename": filename or "Готовая смета",
            "uploaded_at": uploaded_at,
            "source": "crm_estimator_upload",
        }

        estimate_request = data.get("estimate_request")
        if not isinstance(estimate_request, dict):
            estimate_request = {}
        prepared_at = uploaded_at
        duration_minutes = self._duration_minutes(
            estimate_request.get("requested_at"),
            prepared_at,
        )
        estimate_request.update(
            {
                "status": "ready_to_send",
                "final_file": file_record,
                "final_uploaded_at": uploaded_at,
                "prepared_at": prepared_at,
                "duration_minutes": duration_minutes,
                "duration_hours": round(duration_minutes / 60, 2) if duration_minutes is not None else None,
                "sla_met": duration_minutes <= (int(estimate_request.get("sla_hours") or 24) * 60)
                if duration_minutes is not None
                else None,
            }
        )
        data["estimate_request"] = estimate_request

        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        lead.status = LeadStatus.ESTIMATE.value
        await db.commit()
        await db.refresh(lead)
        return file_record

    async def send_final_file_to_lead(
        self,
        db: AsyncSession,
        lead: Lead,
        *,
        message_text: str,
    ) -> dict[str, Any]:
        data = self._parse_extracted_data(lead.extracted_data)
        estimate_request = data.get("estimate_request") if isinstance(data.get("estimate_request"), dict) else {}
        final_file = estimate_request.get("final_file") if isinstance(estimate_request.get("final_file"), dict) else None
        if not final_file or not final_file.get("url"):
            raise ValueError("final_estimate_file_missing")

        file_path = media_path_service.resolve_local_media_path(str(final_file["url"]))
        if not file_path.exists():
            raise ValueError("final_estimate_file_not_found")

        from src.services.estimate_delivery_service import estimate_delivery_service

        telegram_message_id = await estimate_delivery_service.send_telegram_document(
            db=db,
            lead=lead,
            text=message_text,
            file_path=file_path,
        )

        sent_at = datetime.now(timezone.utc).isoformat()
        estimate_request["status"] = "sent"
        estimate_request["sent_at"] = sent_at
        data["estimate_request"] = estimate_request
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        lead.status = LeadStatus.ESTIMATE_SENT.value
        await db.commit()
        await db.refresh(lead)

        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=message_text,
            media_url=str(final_file["url"]),
            telegram_message_id=telegram_message_id,
            sender_name="CRM",
            ai_metadata={"source": "CRM", "type": "final_estimate_sent"},
            status=MessageStatus.SENT,
            transport=MessageTransport.TELEGRAM,
        )
        return final_file

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

    def _duration_minutes(self, start_value: Any, end_value: str) -> int | None:
        start = self._parse_datetime(start_value)
        end = self._parse_datetime(end_value)
        if not start or not end:
            return None
        return max(0, round((end - start).total_seconds() / 60))

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)


estimate_request_service = EstimateRequestService()
