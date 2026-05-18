from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class FunnelSession(BaseModel):
    """One visitor journey through a marketing funnel such as the renovation quiz."""

    __tablename__ = "funnel_sessions"
    __table_args__ = (
        Index("ix_funnel_sessions_org_status_last_event", "org_id", "status", "last_event_at"),
        Index("ix_funnel_sessions_org_source_created", "org_id", "source", "created_at"),
    )

    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)

    session_token = Column(String(64), nullable=False, unique=True, index=True)
    funnel_name = Column(String(100), nullable=False, default="renovation_quiz", index=True)
    channel = Column(String(50), nullable=True, index=True)
    source = Column(String(100), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="started", index=True)
    current_step = Column(String(100), nullable=True)

    utm_source = Column(String(255), nullable=True, index=True)
    utm_medium = Column(String(255), nullable=True)
    utm_campaign = Column(String(255), nullable=True, index=True)
    utm_content = Column(String(255), nullable=True)
    utm_term = Column(String(255), nullable=True)
    entry_url = Column(String(1000), nullable=True)
    referrer = Column(String(1000), nullable=True)
    metadata_json = Column(JSONB, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    abandoned_at = Column(DateTime(timezone=True), nullable=True)
    last_event_at = Column(DateTime(timezone=True), nullable=True, index=True)

    events = relationship("FunnelEvent", back_populates="session", cascade="all, delete-orphan")


class FunnelEvent(BaseModel):
    """Append-only event inside a funnel session."""

    __tablename__ = "funnel_events"
    __table_args__ = (
        Index("ix_funnel_events_org_event_created", "org_id", "event_type", "created_at"),
        Index("ix_funnel_events_session_created", "session_id", "created_at"),
        Index("ix_funnel_events_org_step_created", "org_id", "step_id", "created_at"),
    )

    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("funnel_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)

    event_type = Column(String(100), nullable=False, index=True)
    step_id = Column(String(100), nullable=True, index=True)
    event_data = Column(JSONB, nullable=True)

    session = relationship("FunnelSession", back_populates="events")
