from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, cast, Date
from datetime import datetime, timedelta, date
import uuid
from typing import List

from src.models import Lead, ChatMessage, MessageDirection, LeadStatus
from src.schemas.dashboard import DashboardMetrics, ActivityChartItem, ConversionChartItem, RecentAIAction

# Days in Russian
DAYS_RU = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']


class DashboardService:
    @staticmethod
    async def get_metrics(db: AsyncSession, org_id: uuid.UUID) -> DashboardMetrics:
        # 1. Total leads
        total_leads_query = select(func.count(Lead.id)).where(Lead.org_id == org_id)
        total_leads = (await db.execute(total_leads_query)).scalar() or 0

        # 2. Appointments (leads in MEASUREMENT, ESTIMATE, CONTRACT, WON)
        appointments_query = select(func.count(Lead.id)).where(
            Lead.org_id == org_id,
            Lead.status.in_([
                LeadStatus.MEASUREMENT,
                LeadStatus.ESTIMATE,
                LeadStatus.CONTRACT,
                LeadStatus.WON
            ])
        )
        appointments = (await db.execute(appointments_query)).scalar() or 0

        # 3. In Progress
        in_progress_query = select(func.count(Lead.id)).where(
            Lead.org_id == org_id,
            Lead.status.in_([
                LeadStatus.NEW,
                LeadStatus.CONSULTING,
                LeadStatus.FOLLOW_UP,
                LeadStatus.QUALIFIED
            ])
        )
        in_progress = (await db.execute(in_progress_query)).scalar() or 0

        # 4. Conversion rate (Won / Total)
        won_query = select(func.count(Lead.id)).where(
            Lead.org_id == org_id,
            Lead.status == LeadStatus.WON
        )
        won_count = (await db.execute(won_query)).scalar() or 0
        conversion_rate = round((won_count / total_leads * 100), 1) if total_leads > 0 else 0.0

        # 5. Activity Chart (Last 7 days) — single GROUP BY query instead of N+1
        seven_days_ago = datetime.now() - timedelta(days=6)
        seven_days_ago = seven_days_ago.replace(hour=0, minute=0, second=0, microsecond=0)

        activity_query = (
            select(
                cast(Lead.created_at, Date).label("day"),
                func.count(Lead.id).label("count")
            )
            .where(
                Lead.org_id == org_id,
                Lead.created_at >= seven_days_ago
            )
            .group_by(cast(Lead.created_at, Date))
        )
        activity_rows = {row.day: row.count for row in (await db.execute(activity_query)).all()}

        activity_chart = []
        for i in range(6, -1, -1):
            d = (datetime.now() - timedelta(days=i)).date()
            count = activity_rows.get(d, 0)
            activity_chart.append(ActivityChartItem(day=DAYS_RU[d.weekday()], count=count))

        # 6. Conversion Chart (Qualified+ leads per day) — single GROUP BY query
        qualified_statuses = [
            LeadStatus.QUALIFIED,
            LeadStatus.MEASUREMENT,
            LeadStatus.ESTIMATE,
            LeadStatus.CONTRACT,
            LeadStatus.WON
        ]
        conversion_query = (
            select(
                cast(Lead.created_at, Date).label("day"),
                func.count(Lead.id).label("count")
            )
            .where(
                Lead.org_id == org_id,
                Lead.status.in_(qualified_statuses),
                Lead.created_at >= seven_days_ago
            )
            .group_by(cast(Lead.created_at, Date))
        )
        conversion_rows = {row.day: row.count for row in (await db.execute(conversion_query)).all()}

        conversion_chart = []
        for i in range(6, -1, -1):
            d = (datetime.now() - timedelta(days=i)).date()
            count = conversion_rows.get(d, 0)
            conversion_chart.append(ConversionChartItem(day=DAYS_RU[d.weekday()], rate=float(count)))

        # 7. Recent AI Actions — last 5 messages sent by AI
        recent_actions_query = (
            select(ChatMessage, Lead)
            .join(Lead, ChatMessage.lead_id == Lead.id)
            .where(
                Lead.org_id == org_id,
                ChatMessage.sender_name == 'AI'
            )
            .order_by(desc(ChatMessage.created_at))
            .limit(5)
        )
        results = (await db.execute(recent_actions_query)).all()

        recent_ai_actions = []
        for msg, lead in results:
            recent_ai_actions.append(RecentAIAction(
                lead_name=lead.full_name or lead.username or "Неизвестно",
                message_content=msg.content[:100] + "..." if len(msg.content) > 100 else msg.content,
                status=lead.status,
                created_at=msg.created_at,
                lead_id=str(lead.id)
            ))

        return DashboardMetrics(
            total_leads=total_leads,
            appointments=appointments,
            conversion_rate=conversion_rate,
            in_progress=in_progress,
            activity_chart=activity_chart,
            conversion_chart=conversion_chart,
            recent_ai_actions=recent_ai_actions
        )


dashboard_service = DashboardService()
