from sqlalchemy import Column, String, ForeignKey, BigInteger, Enum as SQLEnum, Text, DateTime, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from src.models.base import BaseModel


class LeadStatus(str, enum.Enum):
    """Lead status flow"""
    NEW = "NEW"
    CONSULTING = "CONSULTING"
    FOLLOW_UP = "FOLLOW_UP"
    QUALIFIED = "QUALIFIED"
    MEASUREMENT = "MEASUREMENT"
    ESTIMATE = "ESTIMATE"
    CONTRACT = "CONTRACT"
    WON = "WON"
    LOST = "LOST"
    SPAM = "SPAM"


class ReadinessScore(str, enum.Enum):
    """A/B/C Client readiness score"""
    A = "A"
    B = "B"
    C = "C"


class Lead(BaseModel):
    """
    Lead model for tracking potential clients.
    Leads are qualified through AI conversation and then converted to projects.
    """
    
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint('org_id', 'telegram_id', name='uq_org_telegram_id'),
    )
    
    # Organization (multi-tenant)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Telegram integration (nullable for manually created CRM leads)
    telegram_id = Column(BigInteger, nullable=True, index=True)
    
    # Lead details
    full_name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    username = Column(String(255), nullable=True)  # Telegram username
    
    # Status
    status = Column(
        String(50),
        nullable=False,
        default=LeadStatus.NEW.value,
        index=True
    )
    
    # AI-generated summary of the conversation
    ai_summary = Column(Text, nullable=True)
    
    # AI qualification status
    ai_qualification_status = Column(
        String(50),
        nullable=False,
        default="in_progress"
    )  # in_progress, qualified, not_interested, handoff_required
    
    # A/B/C Readiness Score
    readiness_score = Column(
        String(10),
        nullable=True
    )
    
    # Extracted data from AI conversation (JSON)
    extracted_data = Column(Text, nullable=True)  # JSON string
    
    # Source of the lead (e.g., "telegram", "website", "referral")
    source = Column(String(100), nullable=True)
    
    # Avatar tracking
    avatar_url = Column(String(500), nullable=True)
    
    # Chat tracking
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    unread_count = Column(Integer, nullable=False, default=0)
    
    # Follow-up tracking
    followup_count = Column(Integer, nullable=False, default=0)  # consecutive follow-ups sent
    last_followup_at = Column(DateTime(timezone=True), nullable=True)
    
    # Project connection
    converted_to_project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="leads")
    chat_messages = relationship("ChatMessage", back_populates="lead", cascade="all, delete-orphan")
    project = relationship("Project", foreign_keys=[converted_to_project_id])
    
    def __repr__(self):
        return f"<Lead(id={self.id}, status={self.status}, telegram_id={self.telegram_id})>"
