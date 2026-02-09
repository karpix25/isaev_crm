"""
Pydantic schemas for request/response validation.
"""

from src.schemas.auth import TokenResponse, LoginRequest, TelegramAuthData
from src.schemas.user import UserCreate, UserUpdate, UserResponse
from src.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationResponse
from src.schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatHistoryResponse, SendMessageRequest
from src.schemas.lead import LeadCreate, LeadUpdate, LeadResponse, LeadListResponse

__all__ = [
    "TokenResponse",
    "LoginRequest",
    "TelegramAuthData",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationResponse",
    "ChatMessageCreate",
    "ChatMessageResponse",
    "ChatHistoryResponse",
    "SendMessageRequest",
    "LeadCreate",
    "LeadUpdate",
    "LeadResponse",
    "LeadListResponse",
]
