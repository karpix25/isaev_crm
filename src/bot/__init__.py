from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from typing import Optional

from src.config import settings

# Initialize bot only if token is valid
bot: Optional[Bot] = None
dp = Dispatcher()

try:
    if settings.telegram_bot_token and len(settings.telegram_bot_token) > 10:
        bot = Bot(token=settings.telegram_bot_token)
except Exception as e:
    print(f"⚠️  Failed to initialize Telegram bot: {e}")
    bot = None

# Import handlers to register them (only if bot is available)
if bot:
    from src.bot.handlers import lead_handler, worker_handler

__all__ = ["bot", "dp"]
