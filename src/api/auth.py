from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import sqlalchemy as sa
import logging
import time
from pydantic import BaseModel

from src.database import get_db
from src.models import User, Organization
from src.models.user import UserRole
from src.schemas.auth import TokenResponse
from src.services.auth import auth_service
from src.bot import bot as telegram_bot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

class TelegramBotInfoResponse(BaseModel):
    bot_id: int
    username: str | None = None


_telegram_bot_info_cache: TelegramBotInfoResponse | None = None
_telegram_bot_info_cache_expires_at: float = 0.0


@router.get("/telegram/bot", response_model=TelegramBotInfoResponse)
async def telegram_bot_info():
    """
    Returns bot id/username for Telegram.Login.auth (popup flow from telegram-widget.js).
    Cached in-memory to avoid extra Bot API calls.
    """
    global _telegram_bot_info_cache, _telegram_bot_info_cache_expires_at

    if not telegram_bot:
        raise HTTPException(status_code=500, detail="Telegram bot not initialized")

    now = time.time()
    if _telegram_bot_info_cache and now < _telegram_bot_info_cache_expires_at:
        return _telegram_bot_info_cache

    try:
        me = await telegram_bot.get_me()
        _telegram_bot_info_cache = TelegramBotInfoResponse(bot_id=me.id, username=getattr(me, "username", None))
        _telegram_bot_info_cache_expires_at = now + 60 * 60  # 1 hour
        return _telegram_bot_info_cache
    except Exception as e:
        logger.error("Failed to fetch Telegram bot info: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch Telegram bot info")

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
