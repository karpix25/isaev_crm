from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid

from src.database import get_db
from src.models import User, UserRole, Lead
from src.schemas.chat import ChatHistoryResponse, ChatMessageResponse, SendMessageRequest
from src.services.chat_service import chat_service
from src.services.lead_service import lead_service
from src.dependencies.auth import get_current_user, require_role
from src.bot import bot

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/{lead_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    lead_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """
    Get chat history for a specific lead.
    Requires ADMIN or MANAGER role.
    """
    # Verify lead exists and belongs to user's organization
    lead = await lead_service.get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    if str(lead.org_id) != str(current_user.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get chat history
    messages, total = await chat_service.get_chat_history(db, lead_id, page, page_size)
    
    # Mark messages as read
    await chat_service.mark_messages_as_read(db, lead_id)
    
    return ChatHistoryResponse(
        messages=[ChatMessageResponse.model_validate(msg) for msg in messages],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/{lead_id}/send", response_model=ChatMessageResponse)
async def send_message_to_lead(
    lead_id: uuid.UUID,
    message_data: SendMessageRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """
    Send message to a lead via Telegram.
    Requires ADMIN or MANAGER role.
    """
    # Verify lead exists and belongs to user's organization
    lead = await lead_service.get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    if str(lead.org_id) != str(current_user.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Send message via Telegram
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot is not configured. Please add TELEGRAM_BOT_TOKEN to .env"
        )
    
    try:
        telegram_message = await bot.send_message(
            chat_id=lead.telegram_id,
            text=message_data.content
        )
        telegram_message_id = telegram_message.message_id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send Telegram message: {str(e)}"
        )
    
    # Save message to database
    message = await chat_service.send_outbound_message(
        db=db,
        lead_id=lead_id,
        content=message_data.content,
        media_url=message_data.media_url,
        telegram_message_id=telegram_message_id
    )
    
    return ChatMessageResponse.model_validate(message)


@router.get("/unread", response_model=dict)
async def get_unread_count(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """
    Get total unread message count for the organization.
    Requires ADMIN or MANAGER role.
    """
    count = await chat_service.get_unread_count(db, current_user.org_id)
    
    return {"unread_count": count}
