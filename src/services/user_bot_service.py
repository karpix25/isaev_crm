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
        self._setup_handlers(org_id, client)
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
        
        # Success! Save session
        session_str = client.session.save()
        bot_record = await self._get_or_create_bot_record(db, org_id)
        bot_record.phone = state["phone"]
        bot_record.api_id = state["api_id"]
        bot_record.api_hash = state["api_hash"]
        bot_record.session_string = session_str
        bot_record.is_authorized = True
        bot_record.is_active = True
        bot_record.status = "connected"
        await db.commit()
        
        self._setup_handlers(org_id, client)
        self.clients[org_id] = client
        del self.auth_states[org_id]
        
        return {"status": "success"}

    def _setup_handlers(self, org_id: uuid.UUID, client: TelegramClient):
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
        """Logic to generate AI response and save to CRM with RAG"""
        import json
        import logging
        logger = logging.getLogger(__name__)
        
        # Note: This needs a fresh DB session
        from src.database import async_session_factory
        async with async_session_factory() as db:
            try:
                # 1. Find or create lead
                from src.services.lead_service import lead_service
                
                # Extract sender info safely
                full_name = getattr(sender, 'first_name', '') + " " + getattr(sender, 'last_name', '')
                full_name = full_name.strip() or "Unknown"
                username = getattr(sender, 'username', None)
                
                lead = await lead_service.create_or_get_lead(
                    db=db, 
                    org_id=org_id, 
                    telegram_id=tg_user_id,
                    full_name=full_name,
                    username=username,
                    source="userbot"
                )

                # 2. Save incoming message
                await chat_service.save_incoming_message(
                    db, 
                    lead_id=lead.id, 
                    content=content,
                    telegram_message_id=None
                )
                
                # 3. Check if agent is active for this bot
                bot_record = await self._get_or_create_bot_record(db, org_id)
                if not bot_record.is_active:
                    return

                # 4. Build system prompt
                from src.services.prompt_service import prompt_service
                from src.services.knowledge_service import knowledge_service
                
                config = await prompt_service.get_active_config(db, org_id)
                
                # Get base prompt
                if config and config.system_prompt:
                    base_prompt = config.system_prompt
                else:
                    from src.services.prompts import build_system_prompt
                    base_prompt = build_system_prompt("наша компания")
                
                # Inject custom fields into prompt
                from src.services.custom_field_service import inject_custom_fields_into_prompt
                enhanced_prompt = await inject_custom_fields_into_prompt(db, org_id, base_prompt)
                
                technical_rules = "\n\nCRITICAL: Always respond in valid JSON format. If you need to speak to the user, put your text in the \"message\" field of the JSON."
                system_prompt = f"{enhanced_prompt}{technical_rules}"
                
                # 5. RAG: Search knowledge base for relevant context
                ai_metadata = {}
                try:
                    relevant_docs = await knowledge_service.search_knowledge(
                        db=db,
                        org_id=org_id,
                        query=content,
                        limit=3,
                        embedding_model=config.embedding_model if config else None
                    )
                    
                    if relevant_docs:
                        context_str = "\n\n".join([f"Source: {d.title}\nContent: {d.content}" for d in relevant_docs])
                        system_prompt = f"{system_prompt}\n\nRELEVANT KNOWLEDGE:\n{context_str}\n\nUse this context to answer accurately."
                        
                        ai_metadata["retrieved_context"] = [
                            {"title": d.title, "content": d.content, "id": str(d.id)}
                            for d in relevant_docs
                        ]
                except Exception as rag_err:
                    logger.warning(f"RAG search failed (non-critical): {rag_err}")
                
                # 6. Get conversation history
                history_msgs, _ = await chat_service.get_chat_history(db, lead.id, page_size=20)
                formatted_history = [
                    {"role": "user" if m.direction == MessageDirection.INBOUND else "assistant", "content": m.content}
                    for m in reversed(history_msgs)
                ]
                
                # 7. Generate AI response
                ai_response = await openrouter_service.generate_response(
                    formatted_history, 
                    system_prompt,
                    model=config.llm_model if config else None
                )
                reply_text = ai_response["text"]
                
                # 8. Send reply via User Bot
                await self.send_message(db, org_id, tg_user_id, reply_text)
                    
                # 9. Save outbound message
                ai_metadata["usage"] = ai_response.get("usage")
                await chat_service.send_outbound_message(
                    db,
                    lead_id=lead.id,
                    content=reply_text,
                    sender_name="AI Agent",
                    ai_metadata=ai_metadata
                )
                
                # 10. Update lead with extracted data
                extracted_data = ai_response.get("extracted_data")
                if extracted_data:
                    update_fields = {}
                    if extracted_data.get("client_name") and not lead.full_name:
                        update_fields["full_name"] = extracted_data.get("client_name")
                    if extracted_data.get("phone") and not lead.phone:
                        update_fields["phone"] = extracted_data.get("phone")
                    
                    from src.models.lead import LeadStatus
                    ai_status = extracted_data.get("status")
                    if ai_status and ai_status in [s.value for s in LeadStatus]:
                        update_fields["status"] = ai_status
                    
                    if extracted_data.get("is_hot_lead"):
                        update_fields["ai_qualification_status"] = "qualified"
                    
                    update_fields["extracted_data"] = json.dumps(extracted_data, ensure_ascii=False)
                    
                    if update_fields:
                        await lead_service.update_lead(db=db, lead_id=lead.id, **update_fields)
                        
            except Exception as e:
                logger.error(f"Error processing User Bot message from {tg_user_id}: {e}", exc_info=True)

    async def send_message(self, db: AsyncSession, org_id: uuid.UUID, telegram_id: int, text: str):
        """Send message via User Bot"""
        client = self.clients.get(org_id)
        if not client:
            # Try to restore session if not in memory
            bot_record = await self._get_or_create_bot_record(db, org_id)
            if bot_record.is_authorized and bot_record.session_string:
                try:
                    client = TelegramClient(sessions.StringSession(bot_record.session_string), bot_record.api_id, bot_record.api_hash)
                    await client.connect()
                    if await client.is_user_authorized():
                        self.clients[org_id] = client
                        self._setup_handlers(org_id, client)
                    else:
                        raise Exception("Session invalid")
                except Exception as e:
                    raise Exception(f"Failed to restore User Bot session: {e}")
            else:
                raise Exception("User Bot not connected or not authorized for this organization")

        await client.send_message(telegram_id, text)


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
