from fastapi import APIRouter, Request, HTTPException, Depends, Query
from aiogram.types import Update
import logging
import asyncio
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.bot import bot, dp
from src.services.novofon_service import novofon_service

logger = logging.getLogger(__name__)
router = APIRouter()

async def _process_update(update: Update) -> None:
    try:
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error("Error processing update async: %s", e, exc_info=True)

@router.post("/telegram")
async def telegram_webhook(request: Request):
    """
    Handle incoming Telegram updates via webhook
    """
    if not bot:
        raise HTTPException(status_code=500, detail="Bot not initialized")
        
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        # Acknowledge quickly to avoid Telegram webhook timeouts.
        asyncio.create_task(_process_update(update))
        return {"status": "ok"}
    except Exception as e:
        logger.error("Error processing webhook: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


async def _parse_incoming_payload(request: Request) -> dict[str, Any]:
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        payload = await request.json()
        if isinstance(payload, dict):
            return payload
        return {"payload": payload}

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        normalized: dict[str, Any] = {}
        for key, value in form.multi_items():
            if key in normalized:
                existing = normalized[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    normalized[key] = [existing, value]
            else:
                normalized[key] = value
        return normalized

    body = await request.body()
    if not body:
        return {}

    raw_text = body.decode("utf-8", errors="ignore").strip()
    if not raw_text:
        return {}

    try:
        maybe_json = await request.json()
        if isinstance(maybe_json, dict):
            return maybe_json
        return {"payload": maybe_json}
    except Exception:
        return {"raw": raw_text}


@router.post("/novofon")
async def novofon_webhook(
    request: Request,
    secret: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Receive Novofon call events and send business card message after answered call.
    """
    if not novofon_service.validate_webhook_secret(secret):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    payload = await _parse_incoming_payload(request)
    if not payload:
        return {"status": "ignored", "reason": "empty_payload"}

    try:
        result = await novofon_service.process_webhook_event(db, payload)
        return {"status": "ok", **result}
    except Exception as e:
        logger.error("Error processing Novofon webhook: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process Novofon webhook")
