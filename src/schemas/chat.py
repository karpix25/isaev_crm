from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
import uuid

from src.models.chat_message import MessageDirection, MessageTransport


class ChatMessageCreate(BaseModel):
    """Create new chat message"""
    lead_id: uuid.UUID
    direction: MessageDirection
    content: str
    media_url: Optional[str] = None
    media_filename: Optional[str] = None
    media_mimetype: Optional[str] = None
    media_size: Optional[int] = None
    telegram_message_id: Optional[int] = None
    external_provider: Optional[str] = None
    external_message_id: Optional[str] = None
    external_chat_id: Optional[str] = None
    sender_name: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Chat message response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    lead_id: uuid.UUID
    direction: MessageDirection
    transport: MessageTransport
    content: str
    media_url: Optional[str] = None
    media_filename: Optional[str] = None
    media_mimetype: Optional[str] = None
    media_size: Optional[int] = None
    telegram_message_id: Optional[int] = None
    external_provider: Optional[str] = None
    external_message_id: Optional[str] = None
    external_chat_id: Optional[str] = None
    is_read: bool
    sender_name: Optional[str] = None
    ai_metadata: Optional[dict] = None
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
    media_filename: Optional[str] = None
    media_mimetype: Optional[str] = None
    media_size: Optional[int] = None
    transport: MessageTransport = MessageTransport.TELEGRAM
