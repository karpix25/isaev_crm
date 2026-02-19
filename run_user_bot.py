import asyncio
import logging
import signal
from sqlalchemy import select
from telethon import TelegramClient, sessions

from src.database import async_session_factory
from src.models import TelegramUserBot
from src.services.user_bot_service import user_bot_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("user_bot_worker")

async def start_active_bots():
    """Load all active bots from DB and start them"""
    async with async_session_factory() as db:
        result = await db.execute(
            select(TelegramUserBot).where(
                TelegramUserBot.is_authorized == True,
                TelegramUserBot.is_active == True
            )
        )
        active_bots = result.scalars().all()
        
        logger.info(f"Found {len(active_bots)} active user bots to start")
        
        for bot in active_bots:
            try:
                # Initialize Telethon client from saved session string
                client = TelegramClient(
                    sessions.StringSession(bot.session_string),
                    bot.api_id,
                    bot.api_hash
                )
                
                await client.connect()
                
                if not await client.is_user_authorized():
                    logger.warning(f"Bot for org {bot.org_id} is not authorized in Telegram. Skipping.")
                    continue
                
                # Setup handlers and store in service
                user_bot_service._setup_handlers(bot.org_id, client)
                user_bot_service.clients[bot.org_id] = client
                
                logger.info(f"Successfully started bot for org {bot.org_id}")
                
            except Exception as e:
                logger.error(f"Failed to start bot for org {bot.org_id}: {e}")
                # Update status in DB
                bot.status = "error"
                bot.last_error = str(e)
                await db.commit()

async def main():
    logger.info("Starting Telegram User Bot worker...")
    
    await start_active_bots()
    
    # Keep the script running
    stop_event = asyncio.Event()
    
    # Handle termination signals
    def stop():
        logger.info("Shutdown signal received")
        stop_event.set()
        
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(sig, stop)

    logger.info("Worker is running. Press Ctrl+C to stop.")
    await stop_event.wait()
    
    # Disconnect all clients on exit
    logger.info("Disconnecting all clients...")
    for org_id in list(user_bot_service.clients.keys()):
        await user_bot_service.stop_client(org_id)
        
    logger.info("Worker stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
