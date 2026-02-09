from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
import uuid

from src.models.chat_message import MessageDirection


class ChatMessageCreate(BaseModel):
    """Create new chat message"""
    lead_id: uuid.UUID
    direction: MessageDirection
    content: str
    media_url: Optional[str] = None
    telegram_message_id: Optional[int] = None
    sender_name: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Chat message response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    lead_id: uuid.UUID
    direction: MessageDirection
    content: str
    media_url: Optional[str] = None
    telegram_message_id: Optional[int] = None
    is_read: bool
    sender_name: Optional[str] = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    """Paginated chat history"""
    messages: List[ChatMessageResponse]
    total: int
    page: int
    page_size: int


class SendMessageRequest(BaseModel):
    """Admin sends message to lead"""
    content: str
    media_url: Optional[str] = None
