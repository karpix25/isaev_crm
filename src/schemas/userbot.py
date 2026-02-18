from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class UserBotAuthStart(BaseModel):
    phone: str
    api_id: int
    api_hash: str

class UserBotAuthVerify(BaseModel):
    code: str

class UserBotAuthPassword(BaseModel):
    password: str

class UserBotSettingsUpdate(BaseModel):
    is_active: Optional[bool] = None

class UserBotStatusResponse(BaseModel):
    org_id: UUID
    phone: str
    is_authorized: bool
    is_active: bool
    status: str
    last_error: Optional[str] = None
