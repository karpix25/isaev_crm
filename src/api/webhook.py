from fastapi import APIRouter, Request, HTTPException, Query
from aiogram.types import Update
import logging
import asyncio
import json
import hmac
from sqlalchemy import and_, desc, select

from src.bot import bot, dp
from src.config import settings
from src.database import AsyncSessionLocal
from src.models import ChatMessage, Lead, LeadStatus, MessageDirection, MessageTransport
from src.services.chat_service import chat_service
from src.services.wazzup_service import wazzup_service
from src.services.whatsapp.evolution_client import evolution_client
from src.services.whatsapp.inbound_message_service import whatsapp_inbound_message_service
from src.bot.utils import get_default_org_id

logger = logging.getLogger(__name__)
router = APIRouter()

async def _process_update(update: Update) -> None:
    try:
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error("Error processing update async: %s", e, exc_info=True)


async def _wazzup_message_exists(db, lead_id, wazzup_message_id: str | None) -> bool:
    if not wazzup_message_id:
        return False

    result = await db.execute(
        select(ChatMessage)
        .where(
            and_(
                ChatMessage.lead_id == lead_id,
                ChatMessage.transport == MessageTransport.WHATSAPP,
                ChatMessage.direction == MessageDirection.INBOUND,
            )
        )
        .order_by(desc(ChatMessage.created_at))
        .limit(100)
    )
    messages = result.scalars().all()
    for message in messages:
        metadata = message.ai_metadata or {}
        if str(metadata.get("wazzup_message_id") or "") == str(wazzup_message_id):
            return True
    return False


async def _get_or_create_whatsapp_lead(db, org_id, chat_id: str, sender_name: str | None) -> Lead:
    lead = await wazzup_service.find_lead_by_whatsapp_chat_id(db, org_id=org_id, chat_id=chat_id)
    if lead:
        return lead

    normalized_phone = wazzup_service.normalize_phone(chat_id)
    extracted_data = {
        "messengers": {"whatsapp": True},
        "whatsapp_wa_id": wazzup_service.normalize_phone_digits(chat_id),
    }
    lead = Lead(
        org_id=org_id,
        full_name=(sender_name or "").strip() or None,
        phone=normalized_phone,
        status=LeadStatus.NEW.value,
        source="whatsapp",
        extracted_data=json.dumps(extracted_data, ensure_ascii=False),
        telegram_lookup_status="not_checked",
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


async def _process_wazzup_payload(payload) -> None:
    try:
        incoming_messages = wazzup_service.extract_incoming_messages(payload)
        status_updates = wazzup_service.extract_status_updates(payload)
        async with AsyncSessionLocal() as db:
            if status_updates:
                await wazzup_service.apply_status_updates(db, status_updates)

            if not incoming_messages:
                return

            org_id = await get_default_org_id(db)
            for item in incoming_messages:
                from src.services.quiz_service import quiz_service
                lead = await quiz_service.link_whatsapp_message(
                    db=db,
                    org_id=org_id,
                    text=item.text,
                    chat_id=item.chat_id,
                    sender_name=item.sender_name,
                )
                if not lead:
                    lead = await _get_or_create_whatsapp_lead(
                        db=db,
                        org_id=org_id,
                        chat_id=item.chat_id,
                        sender_name=item.sender_name,
                    )

                if await _wazzup_message_exists(db, lead.id, item.message_id):
                    continue

                await chat_service.save_incoming_message(
                    db=db,
                    lead_id=lead.id,
                    content=item.text,
                    sender_name=item.sender_name or "WhatsApp",
                    ai_metadata={
                        "source": "wazzup",
                        "channel": "whatsapp",
                        "wazzup_channel_id": item.channel_id,
                        "wazzup_message_id": item.message_id,
                    },
                    transport=MessageTransport.WHATSAPP,
                )
    except Exception as exc:
        logger.error("Error processing Wazzup webhook payload: %s", exc, exc_info=True)


async def _process_evolution_payload(payload) -> None:
    try:
        incoming_messages = evolution_client.extract_incoming_messages(payload)
        if not incoming_messages:
            return
        async with AsyncSessionLocal() as db:
            await whatsapp_inbound_message_service.process_messages(db, incoming_messages)
    except Exception as exc:
        logger.error("Error processing Evolution webhook payload: %s", exc, exc_info=True)

@router.post("/telegram")
async def telegram_webhook(request: Request):
    """
    Handle incoming Telegram updates via webhook
    """
    if not bot:
        raise HTTPException(status_code=500, detail="Bot not initialized")

    expected_secret = (settings.telegram_webhook_secret_token or "").strip()
    if expected_secret:
        provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(provided_secret, expected_secret):
            raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")
        
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        # Acknowledge quickly to avoid Telegram webhook timeouts.
        asyncio.create_task(_process_update(update))
        return {"status": "ok"}
    except Exception as e:
        logger.error("Error processing webhook: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wazzup")
async def wazzup_webhook(
    request: Request,
    token: str | None = Query(default=None),
):
    """
    Handle incoming Wazzup webhooks (WhatsApp).
    """
    try:
        auth_header = request.headers.get("Authorization", "")
        bearer_token = auth_header.removeprefix("Bearer").strip() if auth_header else None
        header_token = request.headers.get("X-Wazzup-Token")
        provided_token = token or header_token or bearer_token
        if not wazzup_service.is_valid_webhook_token(provided_token):
            raise HTTPException(status_code=401, detail="Invalid Wazzup webhook token")

        payload = await request.json()
        if isinstance(payload, dict) and payload.get("test") is True:
            return {"status": "ok", "mode": "test"}

        asyncio.create_task(_process_wazzup_payload(payload))
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error in Wazzup webhook endpoint: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process Wazzup webhook")


@router.post("/evolution")
async def evolution_webhook(
    request: Request,
    token: str | None = Query(default=None),
):
    """
    Handle incoming Evolution API webhooks (WhatsApp linked device).
    """
    try:
        auth_header = request.headers.get("Authorization", "")
        bearer_token = auth_header.removeprefix("Bearer").strip() if auth_header else None
        header_token = request.headers.get("X-Evolution-Token") or request.headers.get("X-Webhook-Token")
        provided_token = token or header_token or bearer_token
        if not evolution_client.is_valid_webhook_token(provided_token):
            raise HTTPException(status_code=401, detail="Invalid Evolution webhook token")

        payload = await request.json()
        if isinstance(payload, dict) and payload.get("test") is True:
            return {"status": "ok", "mode": "test"}

        asyncio.create_task(_process_evolution_payload(payload))
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error in Evolution webhook endpoint: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process Evolution webhook")
