import os
import logging
import asyncio
import contextlib
from urllib.parse import urlparse
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.database import init_db, close_db
from src.api import api_router
from src.bot import bot, dp

logger = logging.getLogger(__name__)
telegram_polling_task: asyncio.Task | None = None


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
async def _start_telegram_polling() -> None:
    global telegram_polling_task
    if not bot:
        logger.warning("Telegram bot is not initialized. Polling is unavailable.")
        return
    if telegram_polling_task and not telegram_polling_task.done():
        logger.info("Telegram polling already running")
        return

    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Starting Telegram bot in polling mode")
    telegram_polling_task = asyncio.create_task(
        dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            handle_signals=False,
        )
    )


@app.on_event("startup")
async def startup():
    await init_db()
    
    mode = settings.telegram_update_mode
    if bot and settings.telegram_bot_token:
        try:
            if mode == "polling":
                await _start_telegram_polling()
            elif mode == "webhook":
                if not settings.telegram_webhook_url:
                    logger.warning("Mode=webhook but TELEGRAM_WEBHOOK_URL is empty. Falling back to polling.")
                    await _start_telegram_polling()
                else:
                    logger.info("Setting webhook to: %s", settings.telegram_webhook_url)
                    await bot.set_webhook(settings.telegram_webhook_url, drop_pending_updates=False)
                    info = await bot.get_webhook_info()
                    logger.info(
                        "Telegram webhook info: url=%s pending=%s last_error=%s",
                        getattr(info, "url", None),
                        getattr(info, "pending_update_count", None),
                        getattr(info, "last_error_message", None),
                    )
            else:  # auto
                webhook_url = settings.telegram_webhook_url
                host = (urlparse(webhook_url).hostname or "") if webhook_url else ""
                # Underscore hostnames are non-standard and often fail for Telegram webhook delivery.
                if not webhook_url or "_" in host:
                    logger.warning(
                        "Auto mode picked polling (webhook_url missing or hostname is non-standard): %s",
                        webhook_url or "<empty>",
                    )
                    await _start_telegram_polling()
                else:
                    try:
                        logger.info("Auto mode: setting webhook to %s", webhook_url)
                        await bot.set_webhook(webhook_url, drop_pending_updates=False)
                        info = await bot.get_webhook_info()
                        logger.info(
                            "Telegram webhook info: url=%s pending=%s last_error=%s",
                            getattr(info, "url", None),
                            getattr(info, "pending_update_count", None),
                            getattr(info, "last_error_message", None),
                        )
                    except Exception as e:
                        logger.error("Auto mode webhook setup failed: %s. Falling back to polling.", e)
                        await _start_telegram_polling()
        except Exception as e:
            logger.error("Failed to initialize Telegram updates mode (%s): %s", mode, e, exc_info=True)
            logger.warning("Falling back to polling mode")
            await _start_telegram_polling()
    else:
        if not bot:
            logger.warning("Telegram bot is not initialized. No bot updates will be processed.")
        elif not settings.telegram_bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN is empty. Bot will not receive updates.")
    
    # Start follow-up background loop
    import asyncio
    from src.services.followup_service import start_followup_loop
    asyncio.create_task(start_followup_loop())
    logger.info("Follow-up background loop scheduled")

@app.on_event("shutdown")
async def shutdown():
    global telegram_polling_task
    if telegram_polling_task and not telegram_polling_task.done():
        telegram_polling_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await telegram_polling_task
    if bot:
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
