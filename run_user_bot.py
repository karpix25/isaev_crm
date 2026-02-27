import asyncio
import logging
import signal
from sqlalchemy import select
from telethon import TelegramClient, sessions

from src.database import AsyncSessionLocal
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
    async with AsyncSessionLocal() as db:
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
                    bot.api_hash,
                    device_model="iPhone 15 Pro",
                    system_version="17.4.1",
                    app_version="10.11",
                    lang_code="ru",
                    system_lang_code="ru"
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
            
            async with AsyncSessionLocal() as db:
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
                            bot.api_hash,
                            device_model="iPhone 15 Pro",
                            system_version="17.4.1",
                            app_version="10.11",
                            lang_code="ru",
                            system_lang_code="ru"
                        )

                        
                        await client.connect()
                        if not await client.is_user_authorized():
                            logger.warning(f"Bot for org {bot.org_id} is not authorized. Skipping.")
                            continue
                            
                        # CRITICAL: Populate the in-memory StringSession entity cache
                        # Without this, we cannot send messages by raw integer ID
                        try:
                            logger.info(f"Populating entity cache for org {bot.org_id}...")
                            await client.get_dialogs(limit=100)
                        except Exception as cache_err:
                            logger.warning(f"Failed to populate dialog cache: {cache_err}")
                        
                        user_bot_service._setup_handlers(bot.org_id, client)
                        user_bot_service.clients[bot.org_id] = client
                        logger.info(f"Successfully started bot for org {bot.org_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to start bot for org {bot.org_id}: {e}")
                        
        except Exception as e:
            logger.error(f"Error in worker bot check loop: {e}")
            
        # --- Poll for pending outbound messages ---
        try:
            from src.models import ChatMessage, Lead, MessageDirection, MessageStatus
            from sqlalchemy.orm import selectinload
            
            async with AsyncSessionLocal() as db:
                # Find all OUTBOUND messages with PENDING status
                # joined with Lead to ensure we only process 'userbot' leads
                result = await db.execute(
                    select(ChatMessage)
                    .join(Lead, ChatMessage.lead_id == Lead.id)
                    .where(
                        ChatMessage.direction == MessageDirection.OUTBOUND,
                        ChatMessage.status == MessageStatus.PENDING,
                        Lead.source.in_(["userbot", "CRM"])
                    )
                    .options(selectinload(ChatMessage.lead))
                )
                pending_messages = result.scalars().all()
                
                for msg in pending_messages:
                    client = user_bot_service.clients.get(msg.lead.org_id)
                    if client and client.is_connected():
                        try:
                            # Attempt to get the entity from cache first
                            try:
                                from telethon.tl.types import PeerUser
                                peer = PeerUser(int(msg.lead.telegram_id))
                                try:
                                    # This only checks the local SQLite cache
                                    await client.get_input_entity(peer)
                                except ValueError:
                                    # Cache miss! Force network request to Telegram API to cache the user
                                    logger.info(f"Entity {msg.lead.telegram_id} not in cache, fetching from Telegram API...")
                                    try:
                                        await client.get_entity(peer)
                                    except ValueError:
                                        # Telegram sometimes refuses to fetch by ID alone without access_hash. Try by username if available.
                                        username = getattr(msg.lead, "username", None)
                                        if username:
                                            logger.info(f"Fetching entity by username: {username}")
                                            await client.get_entity(username)
                                        else:
                                            raise
                            except Exception as entity_err:
                                logger.warning(f"Failed to fetch entity for {msg.lead.telegram_id}, attempting to send anyway: {entity_err}")
                                
                            # Send message via userbot
                            sent_msg = await client.send_message(int(msg.lead.telegram_id), msg.content)
                            
                            # Mark as sent
                            msg.status = MessageStatus.SENT
                            if hasattr(sent_msg, 'id'):
                                msg.telegram_message_id = sent_msg.id
                            await db.commit()
                            logger.info(f"Successfully sent pending message {msg.id} to {msg.lead.telegram_id}")
                        except Exception as e:
                            logger.error(f"Failed to send pending message {msg.id}: {e}")
                            # Mark as failed to prevent infinite loops
                            msg.status = MessageStatus.FAILED
                            await db.commit()
        except Exception as e:
            logger.error(f"Error checking pending messages: {e}")

        # Wait for 2 seconds or until stop_event is set
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2)
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
