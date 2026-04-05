from __future__ import annotations

from sqlalchemy import Column, String, BigInteger

from src.models.base import BaseModel


class AuthSession(BaseModel):
    __tablename__ = "auth_sessions"

    status = Column(String(32), nullable=False, default="pending", index=True)
    telegram_id = Column(BigInteger, nullable=True, index=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)

