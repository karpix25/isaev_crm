import os
import logging
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.database import init_db, close_db
from src.api import api_router
from src.bot import bot, dp

logger = logging.getLogger(__name__)


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    openapi_url=f"{settings.api_v1_str}/openapi.json",
)

# CORS middleware
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Add origins from settings if any
if settings.all_cors_origins:
    origins.extend([str(origin) for origin in settings.all_cors_origins])

# Unique origins
origins = list(set(origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if settings.app_env != "development" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lifespan events
@app.on_event("startup")
async def startup():
    await init_db()
    
    # Set Telegram Webhook
    if bot and settings.telegram_bot_token and settings.telegram_webhook_url:
        try:
            logger.info("Setting webhook to: %s", settings.telegram_webhook_url)
            await bot.set_webhook(settings.telegram_webhook_url, drop_pending_updates=True)
            logger.info("Telegram webhook set successfully")
            try:
                info = await bot.get_webhook_info()
                logger.info(
                    "Telegram webhook info: url=%s pending=%s last_error=%s",
                    getattr(info, "url", None),
                    getattr(info, "pending_update_count", None),
                    getattr(info, "last_error_message", None),
                )
            except Exception as e:
                logger.warning("Failed to fetch Telegram webhook info: %s", e)
        except Exception as e:
            logger.error("Failed to set Telegram webhook: %s", e)
            logger.warning("Application will continue without Telegram bot functionality. Please check TELEGRAM_BOT_TOKEN.")
    else:
        if not bot:
            logger.warning("Telegram bot is not initialized. No bot updates will be processed.")
        elif not settings.telegram_webhook_url:
            logger.warning("TELEGRAM_WEBHOOK_URL is empty. Bot will not receive updates (unless polling is used).")
    
    # Start follow-up background loop
    import asyncio
    from src.services.followup_service import start_followup_loop
    asyncio.create_task(start_followup_loop())
    logger.info("Follow-up background loop scheduled")

@app.on_event("shutdown")
async def shutdown():
    await bot.session.close()
    await close_db()

# Include API routes
app.include_router(api_router)

# Mount static files for avatars/media
media_path = os.path.join(os.getcwd(), "media")
os.makedirs(media_path, exist_ok=True)
app.mount("/media", StaticFiles(directory=media_path), name="media")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
