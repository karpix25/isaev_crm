from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ActivityChartItem(BaseModel):
    day: str
    count: int

class ConversionChartItem(BaseModel):
    day: str
    rate: float

class RecentAIAction(BaseModel):
    lead_name: str
    message_content: str
    status: str
    created_at: datetime
    lead_id: str

class DashboardMetrics(BaseModel):
    total_leads: int
    appointments: int
    conversion_rate: float
    in_progress: int
    spam_count: int
    activity_chart: List[ActivityChartItem]
    conversion_chart: List[ConversionChartItem]
    recent_ai_actions: List[RecentAIAction]
