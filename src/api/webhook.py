from fastapi import APIRouter, Request, Response, status
from aiogram.types import Update

from src.bot import bot, dp

router = APIRouter(prefix="/webhook", tags=["Webhook"])


@router.post("/telegram")
async def telegram_webhook(request: Request):
    """
    Telegram webhook endpoint.
    Receives updates from Telegram and processes them via Aiogram dispatcher.
    """
    try:
        # Parse update from request
        update_data = await request.json()
        update = Update(**update_data)
        
        # Feed update to dispatcher
        await dp.feed_update(bot=bot, update=update)
        
        return Response(status_code=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
