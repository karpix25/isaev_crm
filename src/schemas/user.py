from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
import uuid

from src.models.user import UserRole


class UserBase(BaseModel):
    """Base user schema"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole = UserRole.CLIENT


class UserCreate(UserBase):
    """User creation schema"""
    password: Optional[str] = None
    telegram_id: Optional[int] = None
    org_id: uuid.UUID


class UserUpdate(BaseModel):
    """User update schema"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None


class UserResponse(UserBase):
    """User response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    org_id: uuid.UUID
    telegram_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
