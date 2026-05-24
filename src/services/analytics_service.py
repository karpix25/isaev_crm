import secrets
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import FunnelEvent, FunnelSession
from src.schemas.analytics import (
    AnalyticsEventItem,
    AnalyticsSummary,
    BreakdownItem,
    FunnelSessionCreate,
    FunnelStepMetric,
    MessengerMetric,
    QuizAnswerBreakdown,
)
from src.services.posthog_service import posthog_service


FUNNEL_STEPS: list[tuple[str, str]] = [
    ("quiz_opened", "Открыл квиз"),
    ("quiz_started", "Начал квиз"),
    ("answer_selected", "Ответил на вопросы"),
    ("contact_gate_viewed", "Увидел сохранение расчета"),
    ("contact_gate_submitted", "Сохранил контакт в квизе"),
    ("contact_viewed", "Дошел до контактов"),
    ("contact_submitted", "Оставил контакты"),
    ("lead_created", "Создан лид"),
    ("measurement_booking_requested", "Выбрал время замера"),
    ("measurement_booked", "Замер записан"),
    ("messenger_clicked", "Нажал мессенджер"),
    ("messenger_message_received", "Написал в мессенджер"),
]

QUIZ_STEP_LABELS = {
    "type": "Объект",
    "area": "Площадь",
    "rtype": "Тип ремонта",
    "state": "Состояние",
    "rooms": "Объем",
    "design": "Дизайн-проект",
    "deadline": "Срок старта",
    "budget": "Бюджет",
}


class AnalyticsService:
    async def create_session(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        data: FunnelSessionCreate,
        lead_id: uuid.UUID | None = None,
    ) -> FunnelSession:
        now = datetime.now(timezone.utc)
        session = FunnelSession(
            org_id=org_id,
            lead_id=lead_id,
            session_token=f"qz_{secrets.token_urlsafe(18)}",
            funnel_name=data.funnel_name,
            channel=data.channel,
            source=data.source,
            status="started",
            utm_source=data.utm_source,
            utm_medium=data.utm_medium,
            utm_campaign=data.utm_campaign,
            utm_content=data.utm_content,
            utm_term=data.utm_term,
            entry_url=data.entry_url,
            referrer=data.referrer,
            metadata_json=data.metadata,
            started_at=now,
            last_event_at=now,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def record_event(
        self,
        db: AsyncSession,
        session_token: str,
        event_type: str,
        step_id: str | None = None,
        event_data: dict[str, Any] | None = None,
    ) -> FunnelEvent:
        result = await db.execute(
            select(FunnelSession).where(FunnelSession.session_token == session_token)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError("Funnel session not found")

        now = datetime.now(timezone.utc)
        event = FunnelEvent(
            org_id=session.org_id,
            session_id=session.id,
            lead_id=session.lead_id,
            event_type=event_type,
            step_id=step_id,
            event_data=event_data,
        )
        db.add(event)

        session.last_event_at = now
        if step_id:
            session.current_step = step_id
        if event_type == "quiz_completed":
            session.status = "completed"
            session.completed_at = now
        elif event_type == "quiz_abandoned":
            session.status = "abandoned"
            session.abandoned_at = now
        elif event_type == "lead_created" and event_data and event_data.get("lead_id"):
            try:
                session.lead_id = uuid.UUID(str(event_data["lead_id"]))
                event.lead_id = session.lead_id
            except Exception:
                pass

        await db.flush()
        if session.lead_id:
            from src.services.lead_stage_engine_service import lead_stage_engine_service
            await lead_stage_engine_service.apply_for_session(
                db=db,
                session=session,
                event_type=event_type,
                source="funnel_event",
            )

        await db.commit()
        await db.refresh(event)
        await posthog_service.capture(
            distinct_id=session.session_token,
            event=event_type,
            properties={
                "session_token": session.session_token,
                "funnel_name": session.funnel_name,
                "org_id": str(session.org_id),
                "lead_id": str(event.lead_id) if event.lead_id else None,
                "step_id": step_id,
                "source": session.source,
                "channel": session.channel,
                "utm_source": session.utm_source,
                "utm_medium": session.utm_medium,
                "utm_campaign": session.utm_campaign,
                "utm_content": session.utm_content,
                "utm_term": session.utm_term,
                "event_data": event_data or {},
            },
        )
        return event

    async def get_summary(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        source: str | None = None,
        campaign: str | None = None,
    ) -> AnalyticsSummary:
        session_filters = [FunnelSession.org_id == org_id]
        event_filters = [FunnelEvent.org_id == org_id]
        if date_from:
            session_filters.append(FunnelSession.created_at >= date_from)
            event_filters.append(FunnelEvent.created_at >= date_from)
        if date_to:
            session_filters.append(FunnelSession.created_at <= date_to)
            event_filters.append(FunnelEvent.created_at <= date_to)
        if source:
            session_filters.append(FunnelSession.source == source)
        if campaign:
            session_filters.append(FunnelSession.utm_campaign == campaign)

        session_ids_stmt = select(FunnelSession.id).where(*session_filters)
        event_filters.append(FunnelEvent.session_id.in_(session_ids_stmt))

        sessions_total = await self._scalar_count(db, select(func.count(FunnelSession.id)).where(*session_filters))
        sessions_completed = await self._scalar_count(
            db, select(func.count(FunnelSession.id)).where(*session_filters, FunnelSession.status == "completed")
        )
        sessions_abandoned = await self._scalar_count(
            db, select(func.count(FunnelSession.id)).where(*session_filters, FunnelSession.status == "abandoned")
        )
        leads_linked = await self._scalar_count(
            db, select(func.count(distinct(FunnelSession.lead_id))).where(*session_filters, FunnelSession.lead_id.isnot(None))
        )

        funnel = await self._build_funnel(db, event_filters)
        sources = await self._breakdown(db, FunnelSession.source, session_filters)
        campaigns = await self._breakdown(db, FunnelSession.utm_campaign, session_filters)
        channels = await self._breakdown(db, FunnelSession.channel, session_filters)
        quiz_answers = await self._quiz_answers(db, event_filters)
        messenger_metrics = await self._messenger_metrics(db, event_filters)
        recent_events = await self._recent_events(db, event_filters)

        completion_rate = round((sessions_completed / sessions_total) * 100, 1) if sessions_total else 0.0
        return AnalyticsSummary(
            sessions_total=sessions_total,
            sessions_completed=sessions_completed,
            sessions_abandoned=sessions_abandoned,
            leads_linked=leads_linked,
            completion_rate=completion_rate,
            funnel=funnel,
            sources=sources,
            campaigns=campaigns,
            channels=channels,
            quiz_answers=quiz_answers,
            messenger_metrics=messenger_metrics,
            recent_events=recent_events,
        )

    async def _scalar_count(self, db: AsyncSession, stmt) -> int:
        result = await db.execute(stmt)
        return int(result.scalar() or 0)

    async def _build_funnel(self, db: AsyncSession, filters: list[Any]) -> list[FunnelStepMetric]:
        previous = None
        start = None
        rows: list[FunnelStepMetric] = []
        for event_type, label in FUNNEL_STEPS:
            if event_type == "messenger_clicked":
                event_filter = FunnelEvent.event_type.in_(["telegram_clicked", "whatsapp_clicked"])
            elif event_type == "messenger_message_received":
                event_filter = FunnelEvent.event_type.in_(["telegram_message_received", "whatsapp_message_received"])
            else:
                event_filter = FunnelEvent.event_type == event_type
            count = await self._scalar_count(
                db,
                select(func.count(distinct(FunnelEvent.session_id))).where(*filters, event_filter),
            )
            if start is None:
                start = count
            rows.append(
                FunnelStepMetric(
                    key=event_type,
                    label=label,
                    count=count,
                    conversion_from_previous=round((count / previous) * 100, 1) if previous else None,
                    conversion_from_start=round((count / start) * 100, 1) if start else None,
                )
            )
            previous = count
        return rows

    async def _breakdown(self, db: AsyncSession, column, filters: list[Any]) -> list[BreakdownItem]:
        result = await db.execute(
            select(column, func.count(FunnelSession.id))
            .where(*filters)
            .group_by(column)
            .order_by(func.count(FunnelSession.id).desc())
            .limit(12)
        )
        return [
            BreakdownItem(key=str(key or "unknown"), label=str(key or "Не указано"), count=int(count or 0))
            for key, count in result.all()
        ]

    async def _quiz_answers(self, db: AsyncSession, filters: list[Any]) -> list[QuizAnswerBreakdown]:
        items: list[QuizAnswerBreakdown] = []
        for step_id, label in QUIZ_STEP_LABELS.items():
            value_expr = FunnelEvent.event_data["value"].as_string()
            label_expr = FunnelEvent.event_data["label"].as_string()
            result = await db.execute(
                select(
                    value_expr,
                    label_expr,
                    func.count(FunnelEvent.id),
                )
                .where(*filters, FunnelEvent.event_type == "answer_selected", FunnelEvent.step_id == step_id)
                .group_by(value_expr, label_expr)
                .order_by(func.count(FunnelEvent.id).desc())
                .limit(10)
            )
            options = [
                BreakdownItem(key=str(value or "unknown"), label=str(option_label or value or "Не указано"), count=int(count or 0))
                for value, option_label, count in result.all()
            ]
            items.append(QuizAnswerBreakdown(step_id=step_id, label=label, options=options))
        return items

    async def _messenger_metrics(self, db: AsyncSession, filters: list[Any]) -> list[MessengerMetric]:
        rows: list[MessengerMetric] = []
        configs = [
            ("telegram", "Telegram", "telegram_clicked", "telegram_message_received"),
            ("whatsapp", "WhatsApp", "whatsapp_clicked", "whatsapp_message_received"),
        ]
        for messenger, label, click_event, inbound_event in configs:
            clicked_session_ids = select(FunnelEvent.session_id).where(*filters, FunnelEvent.event_type == click_event)
            clicks = await self._scalar_count(
                db,
                select(func.count(distinct(FunnelEvent.session_id))).where(*filters, FunnelEvent.event_type == click_event),
            )
            inbound = await self._scalar_count(
                db,
                select(func.count(distinct(FunnelEvent.session_id))).where(
                    *filters,
                    FunnelEvent.event_type == inbound_event,
                    FunnelEvent.session_id.in_(clicked_session_ids),
                ),
            )
            rows.append(
                MessengerMetric(
                    messenger=messenger,
                    label=label,
                    clicks=clicks,
                    inbound=inbound,
                    conversion_rate=round((inbound / clicks) * 100, 1) if clicks else 0.0,
                    lost_after_click=max(clicks - inbound, 0),
                )
            )
        return rows

    async def _recent_events(self, db: AsyncSession, filters: list[Any]) -> list[AnalyticsEventItem]:
        result = await db.execute(
            select(FunnelEvent, FunnelSession.session_token)
            .join(FunnelSession, FunnelEvent.session_id == FunnelSession.id)
            .where(*filters)
            .order_by(FunnelEvent.created_at.desc())
            .limit(100)
        )
        return [
            AnalyticsEventItem(
                id=event.id,
                session_token=session_token,
                lead_id=event.lead_id,
                event_type=event.event_type,
                step_id=event.step_id,
                event_data=event.event_data,
                created_at=event.created_at,
            )
            for event, session_token in result.all()
        ]


analytics_service = AnalyticsService()
