from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import sqlalchemy as sa
import logging
from pydantic import BaseModel
from typing import Literal, Optional

from src.database import get_db
from src.models import User, Organization
from src.models.user import UserRole
from src.schemas.auth import TokenResponse
from src.services.auth import auth_service
from src.services.telegram_bot_login_service import telegram_bot_login_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class TelegramBotLoginStartResponse(BaseModel):
    state: str
    expires_in: int


class TelegramBotLoginStatusResponse(BaseModel):
    status: Literal["pending", "approved", "expired"]
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


async def _get_or_create_user_by_telegram(
    db: AsyncSession,
    telegram_id: int,
    full_name: str | None = None,
    username: str | None = None,
) -> User:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user:
        return user

    # Check if database is completely empty (0 users)
    count_result = await db.execute(select(sa.func.count(User.id)))
    total_users = count_result.scalar() or 0

    if total_users != 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found. Please contact administrator.",
        )

    logger.info("Initializing empty database with first Telegram Admin!")

    # Create a default organization since none exists
    organization = Organization(name="Default Organization")
    db.add(organization)
    await db.flush()  # to get organization.id

    # Create the admin user
    user = User(
        org_id=organization.id,
        telegram_id=telegram_id,
        role=UserRole.ADMIN,
        full_name=full_name,
        username=username,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/telegram", response_model=TokenResponse)
async def telegram_auth(
    auth_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Telegram widget authentication.
    Bootstraps the first user as ADMIN if the database is empty.
    """
    # Validate Telegram auth data from widget
    if not auth_service.validate_telegram_widget_auth(auth_data.copy()):
        # Try Mini App validation as fallback just in case
        if not auth_service.validate_telegram_auth(auth_data.copy()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram authentication data"
            )
    
    telegram_id = auth_data.get("id")
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No telegram_id provided"
        )

    user = await _get_or_create_user_by_telegram(
        db=db,
        telegram_id=int(telegram_id),
        full_name=" ".join(
            [p for p in [auth_data.get("first_name"), auth_data.get("last_name")] if p]
        )
        or None,
        username=auth_data.get("username"),
    )
    
    # Create tokens
    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/telegram/bot/start", response_model=TelegramBotLoginStartResponse)
async def telegram_bot_login_start():
    state, expires_in = await telegram_bot_login_service.create_session()
    return TelegramBotLoginStartResponse(state=state, expires_in=expires_in)


@router.get("/telegram/bot/status", response_model=TelegramBotLoginStatusResponse)
async def telegram_bot_login_status(state: str, db: AsyncSession = Depends(get_db)):
    session = await telegram_bot_login_service.get_session(state)
    if not session:
        return TelegramBotLoginStatusResponse(status="expired")

    if not session.telegram_id:
        return TelegramBotLoginStatusResponse(status="pending")

    user = await _get_or_create_user_by_telegram(
        db=db,
        telegram_id=session.telegram_id,
        full_name=session.full_name,
        username=session.username,
    )

    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})
    await telegram_bot_login_service.consume_session(state)

    return TelegramBotLoginStatusResponse(
        status="approved",
        access_token=access_token,
        refresh_token=refresh_token,
    )
