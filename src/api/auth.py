from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import sqlalchemy as sa
import logging

from src.database import get_db
from src.models import User
from src.schemas.auth import LoginRequest, TokenResponse
from src.services.auth import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Admin/Manager login with email and password.
    Returns JWT access and refresh tokens.
    """
    email = credentials.email.lower() if credentials.email else ""
    
    # Find user by email (case-insensitive)
    result = await db.execute(
        select(User).where(sa.func.lower(User.email) == email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning("Login failed - User not found for email: %s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.password_hash:
        logger.warning("Login failed - User %s has no password_hash", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not auth_service.verify_password(credentials.password, user.password_hash):
        logger.warning("Login failed - Incorrect password for user: %s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create tokens
    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/telegram", response_model=TokenResponse)
async def telegram_auth(
    auth_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Telegram user authentication using initData validation.
    Creates user if doesn't exist.
    """
    # Validate Telegram auth data
    if not auth_service.validate_telegram_auth(auth_data):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram authentication data"
        )
    
    telegram_id = auth_data.get("id")
    
    # Find or create user
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please contact administrator."
        )
    
    # Create tokens
    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )
