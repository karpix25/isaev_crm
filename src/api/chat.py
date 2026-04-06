from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid
import re

from src.database import get_db
from src.models import Lead, MessageDirection, MessageTransport, Organization, User, UserRole
from src.schemas.chat import ChatHistoryResponse, ChatMessageResponse, ChatMessageCreate, SendMessageRequest
from src.services.chat_service import chat_service
from src.services.lead_service import lead_service
from src.dependencies.auth import get_current_user, require_role
from src.bot import bot
from src.config import settings

router = APIRouter(prefix="/chat", tags=["Chat"])

TELEGRAM_BUSINESS_CARD_VARIABLES = {
    "client_name",
    "client_full_name",
    "operator_name",
    "operator_username",
    "operator_phone",
    "company_name",
}


def _first_name(full_name: str | None, username: str | None) -> str:
    candidate = (full_name or "").strip()
    if candidate:
        return candidate.split()[0]
    return (username or "").strip().replace("@", "")


def _render_business_card_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key in TELEGRAM_BUSINESS_CARD_VARIABLES:
        rendered = rendered.replace(f"{{{{{key}}}}}", (values.get(key) or "").strip())

    rendered = re.sub(r"[ \t]{2,}", " ", rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip()


@router.get("/{lead_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    lead_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    transport: MessageTransport | None = Query(None),
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
    messages, total = await chat_service.get_chat_history(db, lead_id, page, page_size, transport=transport)
    
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
    
    if not lead.telegram_id:
        if message_data.transport == MessageTransport.TELEGRAM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot send message: This lead has no associated Telegram account."
            )

    if message_data.transport == MessageTransport.WHATSAPP:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp transport is not connected yet. Select Telegram channel.",
        )

    # Send message via Telegram
    telegram_message_id = None
    if lead.source != "userbot" and lead.source != "CRM":
        # Send via Official Bot
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

    # Save message to database (UserBot messages will be picked up by the worker because status defaults to PENDING)
    message = await chat_service.send_outbound_message(
        db=db,
        lead_id=lead_id,
        content=message_data.content,
        media_url=message_data.media_url,
        telegram_message_id=telegram_message_id,
        ai_metadata={"source": "CRM"},
        transport=message_data.transport,
    )

    
    return ChatMessageResponse.model_validate(message)


@router.post("/{lead_id}/send-business-card", response_model=ChatMessageResponse)
async def send_business_card_to_lead(
    lead_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    """
    Send organization-configured Telegram business card template to lead.
    This message is excluded from Knowledge Base indexing.
    """
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

    if not lead.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send business card: this lead has no associated Telegram account."
        )

    org_result = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    organization = org_result.scalar_one_or_none()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    template = (
        (organization.telegram_business_card_template or "").strip()
        or (settings.telegram_business_card_default_template or "").strip()
    )
    if not template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram business card template is empty."
        )

    operator_username = (current_user.username or "").strip().replace("@", "")
    message_content = _render_business_card_template(
        template=template,
        values={
            "client_name": _first_name(lead.full_name, lead.username),
            "client_full_name": (lead.full_name or "").strip(),
            "operator_name": (current_user.full_name or "").strip() or "Ваш менеджер",
            "operator_username": f"@{operator_username}" if operator_username else "",
            "operator_phone": (current_user.phone or "").strip(),
            "company_name": (organization.name or "").strip(),
        },
    )
    if not message_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rendered business card message is empty. Check template variables."
        )

    telegram_message_id = None
    if lead.source != "userbot" and lead.source != "CRM":
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Telegram bot is not configured. Please add TELEGRAM_BOT_TOKEN to .env"
            )
        try:
            telegram_message = await bot.send_message(
                chat_id=lead.telegram_id,
                text=message_content
            )
            telegram_message_id = telegram_message.message_id
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send Telegram message: {str(e)}"
            )

    message = await chat_service.send_outbound_message(
        db=db,
        lead_id=lead_id,
        content=message_content,
        telegram_message_id=telegram_message_id,
        sender_name=current_user.full_name or current_user.username or "Оператор",
        ai_metadata={
            "source": "CRM",
            "type": "business_card",
            "skip_knowledge_index": True,
        },
        transport=MessageTransport.TELEGRAM,
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
