from sqlalchemy import Column, String, ForeignKey, Enum as SQLEnum, Text, BigInteger, Boolean, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from src.models.base import BaseModel


class MessageDirection(str, enum.Enum):
    """Direction of the message"""
    INBOUND = "inbound"   # From lead to bot
    OUTBOUND = "outbound"  # From bot/manager to lead

class MessageStatus(str, enum.Enum):
    """Status of the message delivery"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class ChatMessage(BaseModel):
    """
    Chat message model for storing conversation history.
    Used to display chat interface in the admin panel.
    """
    
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index('ix_chat_messages_lead_id_created_at', 'lead_id', 'created_at'),
    )
    
    # Lead reference
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Message details
    direction = Column(
        SQLEnum(MessageDirection, name="message_direction"),
        nullable=False
    )
    
    status = Column(
        SQLEnum(MessageStatus, name="message_status"),
        nullable=False,
        default=MessageStatus.SENT
    )
    
    content = Column(Text, nullable=False)
    
    # Media URL (if message contains photo/video/document)
    media_url = Column(String(500), nullable=True)
    
    # Telegram message ID for reference
    telegram_message_id = Column(BigInteger, nullable=True)
    
    # Read status (for admin interface)
    is_read = Column(Boolean, nullable=False, default=False)
    
    # Sender display name
    sender_name = Column(String(255), nullable=True)
    
    # AI Metadata (for transparency/RAG logs)
    ai_metadata = Column(JSON, nullable=True) # Storing retrieved context, search queries, etc.
    
    # Relationships
    lead = relationship("Lead", back_populates="chat_messages")
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, direction={self.direction}, lead_id={self.lead_id})>"
