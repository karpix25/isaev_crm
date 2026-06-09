from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field


class FunnelSessionCreate(BaseModel):
    funnel_name: str = "renovation_quiz"
    channel: str | None = None
    source: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    entry_url: str | None = None
    referrer: str | None = None
    metadata: dict[str, Any] | None = None


class FunnelSessionResponse(BaseModel):
    id: uuid.UUID
    session_token: str
    status: str
    current_step: str | None = None

    class Config:
        from_attributes = True


class FunnelEventCreate(BaseModel):
    session_token: str
    event_type: str = Field(min_length=1, max_length=100)
    step_id: str | None = None
    event_data: dict[str, Any] | None = None


class FunnelEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    step_id: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyticsFilters(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    source: str | None = None
    campaign: str | None = None


class FunnelStepMetric(BaseModel):
    key: str
    label: str
    count: int
    conversion_from_previous: float | None = None
    conversion_from_start: float | None = None


class BreakdownItem(BaseModel):
    key: str
    label: str
    count: int


class QuizAnswerBreakdown(BaseModel):
    step_id: str
    label: str
    options: list[BreakdownItem]


class QuizStepMetric(BaseModel):
    step_id: str
    label: str
    index: int
    viewed: int
    answered: int
    dropoffs_after_view: int
    answer_rate: float
    conversion_from_start: float | None = None
    hesitations: int
    back_clicks: int
    avg_time_on_step_ms: int | None = None


class MessengerMetric(BaseModel):
    messenger: str
    label: str
    clicks: int
    inbound: int
    conversion_rate: float
    lost_after_click: int


class AnalyticsEventItem(BaseModel):
    id: uuid.UUID
    session_token: str
    lead_id: uuid.UUID | None = None
    event_type: str
    step_id: str | None = None
    event_data: dict[str, Any] | None = None
    created_at: datetime


class AnalyticsSummary(BaseModel):
    sessions_total: int
    sessions_completed: int
    sessions_abandoned: int
    leads_linked: int
    completion_rate: float
    funnel: list[FunnelStepMetric]
    sources: list[BreakdownItem]
    campaigns: list[BreakdownItem]
    channels: list[BreakdownItem]
    quiz_answers: list[QuizAnswerBreakdown]
    quiz_steps: list[QuizStepMetric]
    messenger_metrics: list[MessengerMetric]
    recent_events: list[AnalyticsEventItem]
