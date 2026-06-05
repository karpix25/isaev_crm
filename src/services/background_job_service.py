import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionLocal
from src.models import BackgroundJob

logger = logging.getLogger(__name__)


class BackgroundJobService:
    async def enqueue(
        self,
        db: AsyncSession,
        job_type: str,
        payload: dict[str, Any],
        max_attempts: int = 3,
        run_at: datetime | None = None,
    ) -> BackgroundJob:
        job = BackgroundJob(
            job_type=job_type,
            payload=payload,
            max_attempts=max(1, max_attempts),
            run_at=run_at or datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    async def enqueue_knowledge_index(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        lead_id: uuid.UUID,
        content: str,
        title: str,
        category: str = "chat_history",
    ) -> BackgroundJob:
        return await self.enqueue(
            db=db,
            job_type="knowledge_index",
            payload={
                "org_id": str(org_id),
                "lead_id": str(lead_id),
                "content": content,
                "title": title,
                "category": category,
            },
        )

    async def claim_jobs(self, db: AsyncSession, batch_size: int) -> list[BackgroundJob]:
        from src.config import settings

        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=max(60, settings.background_job_lock_timeout_seconds))
        await db.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.status == "running",
                BackgroundJob.locked_at.isnot(None),
                BackgroundJob.locked_at < stale_before,
                BackgroundJob.attempts < BackgroundJob.max_attempts,
            )
            .values(status="retry", locked_at=None, run_at=now)
        )
        await db.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.status == "running",
                BackgroundJob.locked_at.isnot(None),
                BackgroundJob.locked_at < stale_before,
                BackgroundJob.attempts >= BackgroundJob.max_attempts,
            )
            .values(status="failed", locked_at=None, finished_at=now, last_error="Job lock expired")
        )

        result = await db.execute(
            select(BackgroundJob)
            .where(
                BackgroundJob.status.in_(["queued", "retry"]),
                BackgroundJob.run_at <= now,
            )
            .order_by(BackgroundJob.run_at.asc(), BackgroundJob.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        jobs = list(result.scalars().all())
        for job in jobs:
            job.status = "running"
            job.attempts = int(job.attempts or 0) + 1
            job.locked_at = now
            job.last_error = None
        await db.commit()
        return jobs

    async def mark_done(self, db: AsyncSession, job: BackgroundJob) -> None:
        job.status = "done"
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()

    async def mark_failed(self, db: AsyncSession, job: BackgroundJob, exc: Exception) -> None:
        now = datetime.now(timezone.utc)
        job.last_error = str(exc)[:4000]
        job.locked_at = None
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.finished_at = now
        else:
            job.status = "retry"
            job.run_at = now + timedelta(seconds=min(300, 30 * max(1, job.attempts)))
        await db.commit()

    async def process_job(self, db: AsyncSession, job: BackgroundJob) -> None:
        if job.job_type == "knowledge_index":
            await self._process_knowledge_index(db, job.payload)
            return
        if job.job_type == "quiz_abandoned_telegram_followup":
            await self._process_quiz_abandoned_telegram_followup(db, job.payload)
            return
        if job.job_type == "measurement_telegram_reminder":
            await self._process_measurement_telegram_reminder(db, job.payload)
            return
        raise ValueError(f"Unknown background job type: {job.job_type}")

    async def _process_knowledge_index(self, db: AsyncSession, payload: dict[str, Any]) -> None:
        from src.services.knowledge_service import knowledge_service

        await knowledge_service.add_knowledge_item(
            db=db,
            org_id=uuid.UUID(payload["org_id"]),
            lead_id=uuid.UUID(payload["lead_id"]) if payload.get("lead_id") else None,
            content=payload["content"],
            category=payload.get("category") or "chat_history",
            title=payload.get("title"),
        )

    async def _process_quiz_abandoned_telegram_followup(self, db: AsyncSession, payload: dict[str, Any]) -> None:
        from src.models import ChatMessage, FunnelEvent, FunnelSession, Lead, MessageStatus, MessageTransport
        from src.services.chat_service import chat_service
        from src.services.user_bot_service import user_bot_service

        session_token = str(payload.get("session_token") or "")
        lead_id = uuid.UUID(str(payload["lead_id"]))

        session_result = await db.execute(select(FunnelSession).where(FunnelSession.session_token == session_token))
        session = session_result.scalar_one_or_none()
        if not session:
            logger.info("Skipping quiz abandoned follow-up: session %s not found", session_token)
            return
        if session.status == "completed" or session.completed_at:
            logger.info("Skipping quiz abandoned follow-up: session %s already completed", session_token)
            return

        lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = lead_result.scalar_one_or_none()
        if not lead or not lead.telegram_id:
            logger.info("Skipping quiz abandoned follow-up: lead %s is not contactable in Telegram", lead_id)
            return

        event_result = await db.execute(
            select(FunnelEvent.event_type).where(
                FunnelEvent.session_id == session.id,
                FunnelEvent.event_type.in_(
                    [
                        "quiz_completed",
                        "telegram_bot_started",
                        "telegram_message_received",
                        "telegram_linked",
                    ]
                ),
            )
        )
        if event_result.first():
            logger.info("Skipping quiz abandoned follow-up: session %s already reached Telegram/completion", session_token)
            return

        history_result = await db.execute(select(ChatMessage).where(ChatMessage.lead_id == lead.id))
        for message in history_result.scalars().all():
            metadata = message.ai_metadata if isinstance(message.ai_metadata, dict) else {}
            if metadata.get("type") == "quiz_abandoned_telegram_followup" and metadata.get("session_token") == session_token:
                logger.info("Skipping quiz abandoned follow-up: already sent for session %s", session_token)
                return

        client_name = (lead.full_name or "").strip()
        greeting = f"{client_name}, здравствуйте!" if client_name else "Здравствуйте!"
        text = (
            f"{greeting} Вы начали расчет ремонта на сайте ISAEV GROUP, но не дошли до конца. "
            "Могу прислать предварительный расчет сюда и помочь продолжить с того места, где остановились?"
        )

        await user_bot_service.send_message(
            db=db,
            org_id=lead.org_id,
            telegram_id=int(lead.telegram_id),
            text=text,
            username=lead.username,
        )
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            sender_name="AI Agent",
            ai_metadata={
                "type": "quiz_abandoned_telegram_followup",
                "session_token": session_token,
                "source": "background_job",
                "skip_knowledge_index": True,
            },
            status=MessageStatus.SENT,
            transport=MessageTransport.TELEGRAM,
        )
        await db.commit()

    async def _process_measurement_telegram_reminder(self, db: AsyncSession, payload: dict[str, Any]) -> None:
        from src.models import Lead
        from src.services.telegram_notification_service import telegram_notification_service

        if not telegram_notification_service.has_recipients("measurement"):
            logger.info("Skipping measurement reminder: no manager Telegram recipients")
            return

        lead_id = uuid.UUID(str(payload["lead_id"]))
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            logger.info("Skipping measurement reminder: lead %s not found", lead_id)
            return

        start = str(payload.get("start") or "")
        address = str(payload.get("address") or "").strip()
        booking_uid = str(payload.get("booking_uid") or "").strip()
        try:
            extracted = json.loads(lead.extracted_data or "{}")
        except json.JSONDecodeError:
            extracted = {}
        measurement = extracted.get("measurement") if isinstance(extracted, dict) else None
        if isinstance(measurement, dict):
            current_start = str(measurement.get("start") or "")
            current_booking_uid = str(measurement.get("booking_uid") or "")
            if (booking_uid and current_booking_uid and booking_uid != current_booking_uid) or (
                start and current_start and start != current_start
            ):
                logger.info(
                    "Skipping stale measurement reminder: lead_id=%s payload_uid=%s current_uid=%s payload_start=%s current_start=%s",
                    lead.id,
                    booking_uid,
                    current_booking_uid,
                    start,
                    current_start,
                )
                return
            address = str(measurement.get("address") or extracted.get("measurement_address") or address).strip()
            if measurement.get("phone") and not lead.phone:
                lead.phone = str(measurement.get("phone"))

        text = (
            "⏰ Напоминание о замере за сутки\n\n"
            f"👤 Клиент: {lead.full_name or 'Клиент квиза'}\n"
            f"📞 Телефон: {lead.phone or 'не указан'}\n"
            f"📅 Дата: {self._format_measurement_start(start)}\n"
            f"📍 Адрес: {address or 'не указан'}\n"
            f"🆔 Лид: {lead.id}"
        )
        if booking_uid:
            text += f"\n🔖 Booking: {booking_uid}"
        sent = await telegram_notification_service.send_to_managers(text, topic="measurement")
        logger.info("Measurement reminder sent: recipients=%s lead_id=%s", sent, lead.id)

    def _format_measurement_start(self, value: str) -> str:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y в %H:%M")
        except Exception:
            return value


background_job_service = BackgroundJobService()


async def start_background_job_loop(stop_event: asyncio.Event | None = None) -> None:
    from src.config import settings

    stop_event = stop_event or asyncio.Event()
    logger.info(
        "Background job loop started (batch=%s interval=%ss)",
        settings.background_job_batch_size,
        settings.background_job_poll_interval_seconds,
    )

    while not stop_event.is_set():
        async with AsyncSessionLocal() as db:
            try:
                jobs = await background_job_service.claim_jobs(
                    db=db,
                    batch_size=max(1, settings.background_job_batch_size),
                )
                for job in jobs:
                    try:
                        await background_job_service.process_job(db, job)
                        await background_job_service.mark_done(db, job)
                        logger.info("Background job %s (%s) completed", job.id, job.job_type)
                    except Exception as exc:
                        logger.error("Background job %s failed: %s", job.id, exc, exc_info=True)
                        await background_job_service.mark_failed(db, job, exc)
            except Exception as exc:
                logger.error("Background job loop failed: %s", exc, exc_info=True)

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=max(1, settings.background_job_poll_interval_seconds),
            )
        except asyncio.TimeoutError:
            continue
