from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
import uuid

from src.models.lead import LeadStatus


class LeadCreate(BaseModel):
    """Create new lead"""
    org_id: uuid.UUID
    telegram_id: Optional[int] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    username: Optional[str] = None
    source: str = "CRM"
    avatar_url: Optional[str] = None


class LeadUpdate(BaseModel):
    """Update lead"""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[LeadStatus] = None
    ai_summary: Optional[str] = None
    avatar_url: Optional[str] = None


class LeadResponse(BaseModel):
    """Lead response with chat preview"""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    org_id: uuid.UUID
    telegram_id: Optional[int] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    username: Optional[str] = None
    status: LeadStatus
    ai_summary: Optional[str] = None
    ai_qualification_status: Optional[str] = "pending"
    extracted_data: Optional[str] = None
    source: Optional[str] = None
    avatar_url: Optional[str] = None
    converted_to_project_id: Optional[uuid.UUID] = None
    last_message_at: Optional[datetime] = None
    unread_count: int
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    """Paginated lead list"""
    leads: List[LeadResponse]
    total: int
    page: int
    page_size: int
