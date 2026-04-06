from fastapi import APIRouter, Request, HTTPException
from aiogram.types import Update
import logging
import asyncio

from src.bot import bot, dp

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
