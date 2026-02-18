from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class TelegramUserBot(BaseModel):
    """
    Model for storing Telegram User Bot (Telethon) settings and sessions.
    Each organization can have one user bot that acts as an agent.
    """
    
    __tablename__ = "telegram_user_bots"
    
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    phone = Column(String(50), nullable=False)
    api_id = Column(Integer, nullable=True)
    api_hash = Column(String(255), nullable=True)
    session_string = Column(Text, nullable=True)
    
    is_authorized = Column(Boolean, default=False)
    is_active = Column(Boolean, default=False)
    
    status = Column(String(50), default="disconnected") # connected, disconnected, error
    last_error = Column(Text, nullable=True)
    
    # Relationships
    organization = relationship("Organization", backref="user_bot")
    
    def __repr__(self):
        return f"<TelegramUserBot(id={self.id}, phone={self.phone}, org_id={self.org_id})>"
