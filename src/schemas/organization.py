from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
import uuid


class OrganizationBase(BaseModel):
    """Base organization schema"""
    name: str = Field(..., min_length=1, max_length=255)


class OrganizationCreate(OrganizationBase):
    """Organization creation schema"""
    owner_id: Optional[uuid.UUID] = None


class OrganizationUpdate(BaseModel):
    """Organization update schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class OrganizationResponse(OrganizationBase):
    """Organization response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    owner_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
