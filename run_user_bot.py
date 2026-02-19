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
    
    # Handle termination signals
    stop_event = asyncio.Event()
    def stop():
        logger.info("Shutdown signal received")
        stop_event.set()
        
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(sig, stop)
        except NotImplementedError:
            # Signal handlers not supported on some platforms (like Windows)
            pass

    while not stop_event.is_set():
        try:
            # Get current running orgs
            running_orgs = list(user_bot_service.clients.keys())
            
            async with async_session_factory() as db:
                result = await db.execute(
                    select(TelegramUserBot).where(
                        TelegramUserBot.is_authorized == True,
                        TelegramUserBot.is_active == True
                    )
                )
                active_bots = result.scalars().all()
                
                for bot in active_bots:
                    if bot.org_id in running_orgs:
                        continue
                        
                    try:
                        logger.info(f"Starting NEW bot for org {bot.org_id}")
                        client = TelegramClient(
                            sessions.StringSession(bot.session_string),
                            bot.api_id,
                            bot.api_hash
                        )
                        
                        await client.connect()
                        if not await client.is_user_authorized():
                            logger.warning(f"Bot for org {bot.org_id} is not authorized. Skipping.")
                            continue
                        
                        user_bot_service._setup_handlers(bot.org_id, client)
                        user_bot_service.clients[bot.org_id] = client
                        logger.info(f"Successfully started bot for org {bot.org_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to start bot for org {bot.org_id}: {e}")
                        
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            
        # Wait for 60 seconds or until stop_event is set
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            continue
    
    # Disconnect all clients on exit
    logger.info("Disconnecting all clients...")
    for org_id in list(user_bot_service.clients.keys()):
        try:
            client = user_bot_service.clients.get(org_id)
            if client:
                await client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting client {org_id}: {e}")
            
    logger.info("Worker stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
