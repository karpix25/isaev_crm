from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
import uuid


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Refresh an access token using a refresh token"""
    refresh_token: str


class LoginRequest(BaseModel):
    """Admin/Manager login request"""
    email: EmailStr
    password: str


class TelegramAuthData(BaseModel):
    """Telegram initData validation"""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str
