from sqlalchemy import Column, String, ForeignKey, BigInteger, Enum as SQLEnum, Text, DateTime, Integer
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


class Lead(BaseModel):
    """
    Lead model for tracking potential clients.
    Leads are qualified through AI conversation and then converted to projects.
    """
    
    __tablename__ = "leads"
    
    # Organization (multi-tenant)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Telegram integration
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    
    # Lead details
    full_name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    username = Column(String(255), nullable=True)  # Telegram username
    
    # Status
    status = Column(
        SQLEnum(LeadStatus, name="lead_status"),
        nullable=False,
        default=LeadStatus.NEW,
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
    
    # Extracted data from AI conversation (JSON)
    extracted_data = Column(Text, nullable=True)  # JSON string
    
    # Source of the lead (e.g., "telegram", "website", "referral")
    source = Column(String(100), nullable=True)
    
    # Avatar tracking
    avatar_url = Column(String(500), nullable=True)
    
    # Chat tracking
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    unread_count = Column(Integer, nullable=False, default=0)
    
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
