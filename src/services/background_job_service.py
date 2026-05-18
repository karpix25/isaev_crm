import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

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
