import asyncio
import os
import uuid
from typing import Dict, Optional, List

from telethon import TelegramClient, events, sessions
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.models.telegram_user_bot import TelegramUserBot
from src.services.openrouter_service import openrouter_service
from src.services.chat_service import chat_service
from src.models import Lead, MessageDirection
from src.config import settings

class UserBotService:
    """
    Service for managing Telegram User Bot (Telethon) clients.
    Handles auth flow, session persistence, and message events.
    """
    
    def __init__(self):
        self.clients: Dict[uuid.UUID, TelegramClient] = {}
        self.auth_states: Dict[uuid.UUID, Dict] = {} # Temporary storage for auth flow

    async def get_client(self, org_id: uuid.UUID, phone: str = None) -> TelegramClient:
        """Get or create Telethon client for an organization"""
        if org_id in self.clients:
            return self.clients[org_id]
        
        # We'll use StringSession for database persistence
        # In a real app, you might want to store the session string in the DB
        return None # To be implemented in start_client

    async def start_auth(self, db: AsyncSession, org_id: uuid.UUID, phone: str, api_id: int, api_hash: str):
        """Step 1: Start auth and send code"""
        client = TelegramClient(sessions.StringSession(), api_id, api_hash)
        await client.connect()
        
        send_code_token = await client.send_code_request(phone)
        
        self.auth_states[org_id] = {
            "client": client,
            "phone": phone,
            "api_id": api_id,
            "api_hash": api_hash,
            "phone_code_hash": send_code_token.phone_code_hash
        }
        
        return {"status": "code_sent"}

    async def verify_code(self, db: AsyncSession, org_id: uuid.UUID, code: str):
        """Step 2: Verify code and save session"""
        state = self.auth_states.get(org_id)
        if not state:
            raise Exception("Auth state not found. Start auth first.")
        
        client = state["client"]
        try:
            await client.sign_in(state["phone"], code, phone_code_hash=state["phone_code_hash"])
        except Exception as e:
            # Check if 2FA is required
            from telethon.errors import SessionPasswordNeededError
            if isinstance(e, SessionPasswordNeededError):
                return {"status": "password_required"}
            raise e
        
        # Success! Save session
        session_str = client.session.save()
        
        # Save to DB
        bot_record = await self._get_or_create_bot_record(db, org_id)
        bot_record.phone = state["phone"]
        bot_record.api_id = state["api_id"]
        bot_record.api_hash = state["api_hash"]
        bot_record.session_string = session_str
        bot_record.is_authorized = True
        bot_record.is_active = True
        bot_record.status = "connected"
        
        await db.commit()
        
        # Start message handler
        self._setup_handlers(org_id, client, db)
        self.clients[org_id] = client
        
        del self.auth_states[org_id]
        return {"status": "success"}

    async def submit_password(self, db: AsyncSession, org_id: uuid.UUID, password: str):
        """Step 3 (Optional): Submit 2FA password"""
        state = self.auth_states.get(org_id)
        if not state:
            raise Exception("Auth state not found")
        
        client = state["client"]
        await client.sign_in(password=password)
        
        # Success! Save session (duplicate from verify_code for simplicity)
        session_str = client.session.save()
        bot_record = await self._get_or_create_bot_record(db, org_id)
        bot_record.session_string = session_str
        bot_record.is_authorized = True
        bot_record.is_active = True
        bot_record.status = "connected"
        await db.commit()
        
        self._setup_handlers(org_id, client, db)
        self.clients[org_id] = client
        del self.auth_states[org_id]
        
        return {"status": "success"}

    def _setup_handlers(self, org_id: uuid.UUID, client: TelegramClient, db_gen):
        """Attach message handlers to the client"""
        
        @client.on(events.NewMessage(incoming=True))
        async def handle_new_message(event):
            if not event.is_private:
                return
            
            # 1. Get sender info
            sender = await event.get_sender()
            sender_id = event.sender_id
            content = event.message.message
            
            # Use a separate background task to avoid blocking the client
            asyncio.create_task(self._process_message(org_id, sender_id, sender, content))

    async def _process_message(self, org_id: uuid.UUID, tg_user_id: int, sender, content: str):
        """Logic to generate AI response and save to CRM"""
        # Note: This needs a fresh DB session
        from src.database import async_session_factory
        async with async_session_factory() as db:
            # 1. Find or create lead
            # Implementation depends on lead_service
            # We'll assume lead_service can find lead by telegram_id
            from src.services.lead_service import lead_service
            lead = await lead_service.get_or_create_by_telegram(db, org_id, tg_user_id, sender)
            
            # 2. Save incoming message
            await chat_service.save_incoming_message(
                db, 
                lead_id=lead.id, 
                content=content,
                telegram_message_id=None # Telethon message id
            )
            
            # 3. Check if agent is active for this bot
            bot_record = await self._get_or_create_bot_record(db, org_id)
            if not bot_record.is_active:
                return

            # 4. Generate AI response
            # Get history
            history_msgs, _ = await chat_service.get_chat_history(db, lead.id, page_size=10)
            formatted_history = [
                {"role": "user" if m.direction == MessageDirection.INBOUND else "assistant", "content": m.content}
                for m in reversed(history_msgs)
            ]
            
            # Get prompt
            from src.services.prompt_service import prompt_service
            system_prompt = await prompt_service.get_active_prompt(db, org_id, "default_agent")
            
            ai_response = await openrouter_service.generate_response(formatted_history, system_prompt)
            reply_text = ai_response["text"]
            
            # 5. Send reply via Telegram
            client = self.clients.get(org_id)
            if client:
                await client.send_message(tg_user_id, reply_text)
                
                # 6. Save outbound message
                await chat_service.send_outbound_message(
                    db,
                    lead_id=lead.id,
                    content=reply_text,
                    sender_name="AI Agent",
                    ai_metadata=ai_response.get("usage")
                )

    async def _get_or_create_bot_record(self, db: AsyncSession, org_id: uuid.UUID) -> TelegramUserBot:
        result = await db.execute(select(TelegramUserBot).where(TelegramUserBot.org_id == org_id))
        bot_record = result.scalars().first()
        if not bot_record:
            bot_record = TelegramUserBot(org_id=org_id, phone="", status="disconnected")
            db.add(bot_record)
        return bot_record

    async def stop_client(self, org_id: uuid.UUID):
        client = self.clients.pop(org_id, None)
        if client:
            await client.disconnect()

# Global singleton
user_bot_service = UserBotService()
