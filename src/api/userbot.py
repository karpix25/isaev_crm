from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_db
from src.dependencies.auth import get_current_user
from src.models import User, TelegramUserBot
from src.schemas.userbot import (
    UserBotAuthStart, UserBotAuthVerify, UserBotAuthPassword, 
    UserBotSettingsUpdate, UserBotStatusResponse
)
from src.services.user_bot_service import user_bot_service

router = APIRouter(prefix="/userbot", tags=["Telegram User Bot"])

@router.get("/status", response_model=UserBotStatusResponse)
async def get_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current user bot status for the organization"""
    result = await db.execute(
        select(TelegramUserBot).where(TelegramUserBot.org_id == current_user.org_id)
    )
    bot = result.scalars().first()
    
    if not bot:
        return {
            "org_id": current_user.org_id,
            "phone": "",
            "is_authorized": False,
            "is_active": False,
            "status": "not_configured"
        }
    
    return bot

@router.post("/auth/start")
async def start_auth(
    data: UserBotAuthStart,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Step 1: Start auth process and send code to phone"""
    try:
        result = await user_bot_service.start_auth(
            db, 
            org_id=current_user.org_id, 
            phone=data.phone, 
            api_id=data.api_id, 
            api_hash=data.api_hash
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/auth/resend-sms")
async def resend_code_via_sms(
    data: UserBotAuthStart,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resend code forcing SMS delivery"""
    try:
        result = await user_bot_service.start_auth(
            db, 
            org_id=current_user.org_id, 
            phone=data.phone, 
            api_id=data.api_id, 
            api_hash=data.api_hash,
            force_sms=True
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/auth/verify")
async def verify_code(
    data: UserBotAuthVerify,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Step 2: Verify code received in Telegram"""
    try:
        result = await user_bot_service.verify_code(
            db, 
            org_id=current_user.org_id, 
            code=data.code
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/auth/password")
async def submit_password(
    data: UserBotAuthPassword,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Step 3: Submit 2FA password if required"""
    try:
        result = await user_bot_service.submit_password(
            db, 
            org_id=current_user.org_id, 
            password=data.password
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.patch("/settings", response_model=UserBotStatusResponse)
async def update_settings(
    data: UserBotSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user bot settings (e.g. toggle is_active)"""
    result = await db.execute(
        select(TelegramUserBot).where(TelegramUserBot.org_id == current_user.org_id)
    )
    bot = result.scalars().first()
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User bot not configured"
        )
    
    if data.is_active is not None:
        bot.is_active = data.is_active
        # If toggled off, we might want to disconnect the client
        if not data.is_active:
            await user_bot_service.stop_client(current_user.org_id)
        else:
            # Toggled on - will be picked up by background worker or re-authed
            pass
            
    await db.commit()
    await db.refresh(bot)
    return bot
