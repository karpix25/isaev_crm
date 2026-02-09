from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
import uuid
from typing import List

from src.models import Lead, ChatMessage, MessageDirection, LeadStatus
from src.schemas.dashboard import DashboardMetrics, ActivityChartItem, ConversionChartItem, RecentAIAction

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

        # 5. Activity Chart (Last 7 days)
        activity_chart = []
        for i in range(6, -1, -1):
            date = datetime.now() - timedelta(days=i)
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            count_query = select(func.count(Lead.id)).where(
                Lead.org_id == org_id,
                Lead.created_at >= start_of_day,
                Lead.created_at <= end_of_day
            )
            count = (await db.execute(count_query)).scalar() or 0
            
            # Days in Russian: Пн, Вт, Ср, Чт, Пт, Сб, Вс
            days_ru = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            day_label = days_ru[date.weekday()]
            activity_chart.append(ActivityChartItem(day=day_label, count=count))

        # 6. Conversion Chart (Qualified leads per day)
        conversion_chart = []
        for i in range(6, -1, -1):
            date = datetime.now() - timedelta(days=i)
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Count leads that reached QUALIFIED status on this day
            # Simplified: checking leads created on this day that are ALREADY qualified or won
            qual_query = select(func.count(Lead.id)).where(
                Lead.org_id == org_id,
                Lead.status.in_([
                    LeadStatus.QUALIFIED, 
                    LeadStatus.MEASUREMENT, 
                    LeadStatus.ESTIMATE, 
                    LeadStatus.CONTRACT, 
                    LeadStatus.WON
                ]),
                Lead.created_at >= start_of_day,
                Lead.created_at <= end_of_day
            )
            count = (await db.execute(qual_query)).scalar() or 0
            
            day_label = days_ru[date.weekday()]
            conversion_chart.append(ConversionChartItem(day=day_label, rate=float(count)))

        # 7. Recent AI Actions
        # Get last 5 messages sent by AI
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
