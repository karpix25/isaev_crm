import asyncio
import os
import random
import uuid
import re
from typing import Dict, Optional, List
import httpx

from telethon import TelegramClient, events, sessions
from telethon import functions, types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.models.telegram_user_bot import TelegramUserBot
from src.services.openrouter_service import openrouter_service
from src.services.chat_service import chat_service
from src.models import Lead, MessageDirection
from src.config import settings
from src.services.business_hours import is_business_hours, get_business_now

import logging
logger = logging.getLogger(__name__)

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

    async def start_auth(self, db: AsyncSession, org_id: uuid.UUID, phone: str, api_id: int, api_hash: str, force_sms: bool = False):
        """Step 1: Start auth and send code"""
        from telethon.errors import FloodWaitError, ApiIdInvalidError, PhoneNumberInvalidError
        
        print(f"[USERBOT] Starting auth for org {org_id}, phone: {phone[:4]}***, force_sms={force_sms}")
        
        # Reuse existing client if we have one in auth_states (for resend)
        if org_id in self.auth_states and not force_sms:
            existing = self.auth_states[org_id]
            client = existing["client"]
        else:
            client = TelegramClient(
                sessions.StringSession(), 
                api_id, 
                api_hash,
                device_model="iPhone 15 Pro",
                system_version="17.4.1",
                app_version="10.11",
                lang_code="ru",
                system_lang_code="ru"
            )
            await client.connect()
        
        print(f"[USERBOT] Telethon client connected: {client.is_connected()}")
        
        try:
            send_code_token = await client.send_code_request(phone, force_sms=force_sms)
        except FloodWaitError as e:
            wait_seconds = e.seconds
            print(f"[USERBOT] ❌ FloodWait! Need to wait {wait_seconds} seconds")
            raise Exception(f"Telegram требует подождать {wait_seconds} секунд перед повторной отправкой кода")
        except ApiIdInvalidError:
            print(f"[USERBOT] ❌ Invalid API ID/Hash!")
            raise Exception("Неверный API ID или API Hash. Проверьте данные на my.telegram.org")
        except PhoneNumberInvalidError:
            print(f"[USERBOT] ❌ Invalid phone number!")
            raise Exception("Неверный формат номера телефона. Используйте формат +79991234567")
        except Exception as e:
            print(f"[USERBOT] ❌ Error: {type(e).__name__}: {e}")
            raise
        
        # Determine code delivery type
        code_type = type(send_code_token.type).__name__
        print(f"[USERBOT] ✅ Code sent! Type: {code_type}, phone_code_hash: {send_code_token.phone_code_hash[:8]}...")
        
        self.auth_states[org_id] = {
            "client": client,
            "phone": phone,
            "api_id": api_id,
            "api_hash": api_hash,
            "phone_code_hash": send_code_token.phone_code_hash
        }
        
        # Map Telethon type names to user-friendly descriptions
        type_map = {
            "SentCodeTypeSms": "sms",
            "SentCodeTypeApp": "app",
            "SentCodeTypeCall": "call",
            "SentCodeTypeFlashCall": "flash_call",
            "SentCodeTypeMissedCall": "missed_call",
            "SentCodeTypeFragmentSms": "fragment_sms",
        }
        delivery = type_map.get(code_type, code_type)
        
        return {"status": "code_sent", "code_type": delivery}

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
        
        # Disconnect temporary client so worker can take over
        await client.disconnect()
        
        del self.auth_states[org_id]
        print(f"[USERBOT] Auth success for org {org_id}. Client disconnected, handed over to worker.")
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
        
        # Disconnect temporary client so worker can take over
        await client.disconnect()
        
        del self.auth_states[org_id]
        print(f"[USERBOT] 2FA success for org {org_id}. Client disconnected, handed over to worker.")
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
            is_voice = False
            image_base64 = None
            photo_caption = ""
            
            # 2. Check for voice/audio/video note
            if event.message.voice or event.message.audio or event.message.video_note:
                import os
                import tempfile
                from src.services.voice_service import voice_service
                
                # Silently download and transcribe
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
                        temp_path = temp_file.name
                        
                    await client.download_media(event.message, file=temp_path)
                    
                    transcript = await voice_service.transcribe_audio(temp_path)
                    
                    # Cleanup
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        
                    if transcript:
                        content = transcript
                        is_voice = True
                        logger.info(f"[USERBOT] Voice transcribed: {content}")
                    else:
                        logger.warning("[USERBOT] Failed to transcribe voice message")
                        return
                        
                except Exception as e:
                    logger.error(f"[USERBOT] Error processing voice message: {e}", exc_info=True)
                    return
            
            # 3. Check for photo messages
            elif event.message.photo:
                photo_caption = event.message.message or "" # caption text if any
                if event.message.fwd_from:
                    content = f"[Клиент переслал фото (возможно, фото объекта для ремонта)]"
                elif photo_caption:
                    content = f"[Клиент прислал фото с подписью] {photo_caption}"
                else:
                    content = "[Клиент прислал фото без текста (возможно, фото объекта для ремонта)]"
                
                # Download and encode for vision
                try:
                    import base64
                    import tempfile
                    import os
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        temp_path = tmp.name
                    await client.download_media(event.message, file=temp_path)
                    with open(temp_path, "rb") as f:
                        image_base64 = base64.b64encode(f.read()).decode("utf-8")
                    os.remove(temp_path)
                    logger.info(f"[USERBOT] Photo downloaded and encoded for vision from {sender_id}")
                except Exception as e:
                    logger.error(f"[USERBOT] Failed to download photo for vision: {e}")

                logger.info(f"[USERBOT] Photo received from {sender_id}: {content}")
            
            # 4. Skip if no content at all
            elif not content:
                return
            
            # Use a separate background task to avoid blocking the client
            asyncio.create_task(self._process_message(
                org_id, sender_id, sender, content, 
                is_voice=is_voice, image_base64=image_base64, photo_caption=photo_caption
            ))

    async def _process_message(self, org_id: uuid.UUID, tg_user_id: int, sender, content: str, 
                               is_voice: bool = False, image_base64: str = None, photo_caption: str = ""):
        """Logic to generate AI response and save to CRM with RAG"""
        import json
        import logging
        logger = logging.getLogger(__name__)
        
        # Note: This needs a fresh DB session
        from src.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            try:
                # 1. Find or create lead
                from src.services.lead_service import lead_service
                
                # Extract sender info safely
                first_name = getattr(sender, 'first_name', '') or ""
                last_name = getattr(sender, 'last_name', '') or ""
                full_name = f"{first_name} {last_name}".strip() or "Unknown"
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
                    telegram_message_id=None,
                    ai_metadata={"is_voice": True} if is_voice else None
                )
                
                # 2.5 Wait a bit to simulate human reading and typing (5-15 seconds)
                delay = random.uniform(5, 15)
                logger.info(f"[USERBOT] Waiting {delay:.2f}s before AI response for lead {lead.id}")
                await asyncio.sleep(delay)
                
                # 3. Check if agent is active for this bot
                bot_record = await self._get_or_create_bot_record(db, org_id)
                if not bot_record.is_active:
                    return

                if not is_business_hours():
                    logger.info(
                        "[USERBOT] Outside business hours at %s, skipping auto-reply for lead %s",
                        get_business_now().isoformat(),
                        lead.id
                    )
                    return

                # 4. Build system prompt
                from src.services.prompt_service import prompt_service
                from src.services.knowledge_service import knowledge_service
                from src.models.organization import Organization
                from sqlalchemy import select
                
                config = await prompt_service.get_active_config(db, org_id)
                org_result = await db.execute(select(Organization).where(Organization.id == org_id))
                org = org_result.scalar_one_or_none()
                company_name = org.name if org else "наша компания"
                
                # Get base prompt
                if config and config.system_prompt:
                    base_prompt = config.system_prompt
                    if "{company_name}" in base_prompt:
                        base_prompt = base_prompt.replace("{company_name}", company_name)
                    from src.services.custom_field_service import enrich_system_prompt
                    system_prompt = await enrich_system_prompt(db, org_id, base_prompt)
                else:
                    from src.services.prompts import build_system_prompt
                    system_prompt = await build_system_prompt(db, org_id, company_name)
                
                from src.services.prompts import IDENTITY_GUARDRAILS, normalize_system_prompt_template
                system_prompt = normalize_system_prompt_template(system_prompt)
                technical_rules = "\n\nCRITICAL: Always respond in valid JSON format. If you need to speak to the user, put your text in the \"message\" field of the JSON."
                identity_rules = IDENTITY_GUARDRAILS.format(company_name=company_name)
                system_prompt = f"{system_prompt}\n\n{identity_rules}{technical_rules}"
                
                client = self.clients.get(org_id)
                typing_context = client.action(int(tg_user_id), 'typing') if client else None
                
                if typing_context:
                    await typing_context.__aenter__()

                try:
                    # 5. RAG: Search knowledge base for relevant context
                    ai_metadata = {}
                    try:
                        relevant_docs = await knowledge_service.search_knowledge(
                            db=db,
                            org_id=org_id,
                            query=content,
                            limit=3,
                            lead_id=lead.id,
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
                    
                    formatted_history = []
                    for m in reversed(history_msgs):
                        role = "user" if m.direction == MessageDirection.INBOUND else "assistant"
                        text_content = m.content
                        
                        # Tell AI if the user sent a voice message
                        if m.ai_metadata and m.ai_metadata.get("is_voice"):
                            text_content = f"[Голосовое сообщение] {text_content}"
                            
                        formatted_history.append({"role": role, "content": text_content})
                    
                    # 7. Generate AI response
                    if image_base64:
                        ai_response = await openrouter_service.generate_vision_response(
                            formatted_history,
                            system_prompt,
                            image_base64=image_base64,
                            image_caption=photo_caption,
                            model=config.llm_model if config else None
                        )
                    else:
                        ai_response = await openrouter_service.generate_response(
                            formatted_history, 
                            system_prompt,
                            model=config.llm_model if config else None
                        )
                finally:
                    if typing_context:
                        await typing_context.__aexit__(None, None, None)
                reply_text = openrouter_service.enforce_identity_answer(
                    user_message=content,
                    ai_text=ai_response["text"],
                    company_name=company_name
                )
                
                # 8. Send reply via User Bot
                await self.send_message(db, org_id, tg_user_id, reply_text)
                    
                # 9. Extract data and detect status changes BEFORE saving message
                extracted_data = ai_response.get("extracted_data")
                update_fields = {}
                if extracted_data:
                    if extracted_data.get("client_name") and not lead.full_name:
                        update_fields["full_name"] = extracted_data.get("client_name")
                    if extracted_data.get("phone") and not lead.phone:
                        update_fields["phone"] = extracted_data.get("phone")
                    
                    from src.models.lead import LeadStatus
                    ai_status = extracted_data.get("status")
                    if ai_status and ai_status in [s.value for s in LeadStatus]:
                        update_fields["status"] = ai_status
                        if lead.status != ai_status:
                            ai_metadata["status_changed_to"] = ai_status
                    
                    if extracted_data.get("is_hot_lead"):
                        update_fields["ai_qualification_status"] = "qualified"
                        if lead.ai_qualification_status != "qualified":
                            ai_metadata["qualification_changed_to"] = "qualified"
                    
                    update_fields["extracted_data"] = json.dumps(extracted_data, ensure_ascii=False)

                # 10. Save outbound message WITH ai_metadata and mark as SENT to prevent duplicate queue send
                from src.models import MessageStatus
                ai_metadata["usage"] = ai_response.get("usage")
                await chat_service.send_outbound_message(
                    db,
                    lead_id=lead.id,
                    content=reply_text,
                    sender_name="AI Agent",
                    ai_metadata=ai_metadata,
                    status=MessageStatus.SENT
                )
                
                # 11. Apply updates to the lead
                if update_fields:
                    await lead_service.update_lead(db=db, lead_id=lead.id, **update_fields)
                        
            except Exception as e:
                logger.error(f"Error processing User Bot message from {tg_user_id}: {e}", exc_info=True)

    async def send_message(self, db: AsyncSession, org_id: uuid.UUID, telegram_id: int, text: str, username: Optional[str] = None):
        """Send message via User Bot with entity resolution fallback"""
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
                    else:
                        raise Exception("Session invalid")
                except Exception as e:
                    raise Exception(f"Failed to restore User Bot session: {e}")
            else:
                raise Exception("User Bot not connected or not authorized for this organization")

        try:
            # Try sending by ID
            await client.send_message(telegram_id, text)
        except ValueError as e:
            # If entity not found in cache, try username if available
            if "Could not find the input entity" in str(e) and username:
                logger.info(f"[USERBOT] ID resolution failed for {telegram_id}, trying username @{username}")
                try:
                    await client.send_message(username, text)
                except Exception as user_err:
                    logger.error(f"[USERBOT] Final send failure for @{username}: {user_err}")
                    raise
            else:
                # If no username or different error
                logger.error(f"[USERBOT] Message send failed: {e}")
                raise

    async def resolve_username(self, db: AsyncSession, org_id: uuid.UUID, username: str) -> Optional[int]:
        """Resolves a Telegram username to a numeric telegram_id using the User Bot"""
        client = await self._get_or_restore_client(db, org_id)
        if not client:
            logger.warning(f"[USERBOT] User Bot not connected or not authorized for org {org_id}. Cannot resolve username {username}.")
            return None

        try:
            # Clean username just in case it has an @
            clean_username = username.strip()
            if clean_username.startswith('@'):
                clean_username = clean_username[1:]
                
            entity = await client.get_entity(clean_username)
            return entity.id
        except Exception as e:
            logger.error(f"[USERBOT] Failed to resolve username '{username}': {e}")
            return None

    async def resolve_phone(self, db: AsyncSession, org_id: uuid.UUID, phone: str) -> Optional[dict]:
        """
        Resolve phone number via Telegram contacts.importContacts.
        Returns dict:
        - {"active": True, telegram_id, username, full_name} if number exists in Telegram
        - {"active": False} if checked and not found in Telegram
        - None if could not check (no userbot/invalid phone/error)
        """
        normalized_phone = self._normalize_phone(phone)
        if not normalized_phone:
            return None

        client = await self._get_or_restore_client(db, org_id)
        if not client:
            logger.warning(f"[USERBOT] User Bot not connected or not authorized for org {org_id}. Cannot resolve phone {phone}.")
            return None

        imported_user = None
        try:
            contact = types.InputPhoneContact(
                client_id=random.randint(10_000, 9_999_999_999),
                phone=normalized_phone,
                first_name="Lead",
                last_name="Lookup",
            )
            result = await client(functions.contacts.ImportContactsRequest([contact]))
            if not result.users:
                return {"active": False}

            imported_user = result.users[0]
            first_name = (getattr(imported_user, "first_name", "") or "").strip()
            last_name = (getattr(imported_user, "last_name", "") or "").strip()
            full_name = f"{first_name} {last_name}".strip() or None

            return {
                "active": True,
                "telegram_id": imported_user.id,
                "username": getattr(imported_user, "username", None),
                "full_name": full_name,
            }
        except Exception as e:
            logger.error(f"[USERBOT] Failed to resolve phone '{normalized_phone}': {e}")
            return None
        finally:
            # Best-effort cleanup: remove imported contact from UserBot contacts
            if imported_user is not None:
                try:
                    await client(functions.contacts.DeleteContactsRequest(id=[imported_user]))
                except Exception as cleanup_err:
                    logger.warning(f"[USERBOT] Failed to cleanup imported contact for {normalized_phone}: {cleanup_err}")

    async def resolve_whatsapp(self, phone: str) -> Optional[dict]:
        """
        Resolve WhatsApp presence via external lookup endpoint.
        Returns dict:
        - {"active": bool, "wa_id": Optional[str]} when check executed
        - None when provider is not configured or request failed
        """
        lookup_url = (settings.whatsapp_lookup_url or "").strip()
        if not lookup_url:
            return None

        normalized_phone = self._normalize_phone(phone)
        if not normalized_phone:
            return None

        headers = {"Accept": "application/json"}
        if settings.whatsapp_lookup_token:
            headers["Authorization"] = f"Bearer {settings.whatsapp_lookup_token}"

        try:
            timeout = max(1, int(settings.whatsapp_lookup_timeout_seconds))
            async with httpx.AsyncClient(timeout=timeout) as client:
                if settings.whatsapp_lookup_method == "get":
                    if "{phone}" in lookup_url:
                        response = await client.get(lookup_url.format(phone=normalized_phone), headers=headers)
                    else:
                        response = await client.get(lookup_url, headers=headers, params={"phone": normalized_phone})
                else:
                    if "{phone}" in lookup_url:
                        response = await client.post(lookup_url.format(phone=normalized_phone), headers=headers)
                    else:
                        response = await client.post(lookup_url, headers=headers, json={"phone": normalized_phone})

            response.raise_for_status()
            payload = response.json() if response.content else {}
            if not isinstance(payload, dict):
                return None

            active = payload.get("active")
            if active is None:
                active = payload.get("exists")
            if active is None:
                active = payload.get("is_whatsapp")
            if active is None:
                active = payload.get("registered")
            if active is None:
                return None

            wa_id = payload.get("wa_id") or payload.get("id")
            return {
                "active": bool(active),
                "wa_id": str(wa_id) if wa_id is not None else None,
            }
        except Exception as e:
            logger.error(f"[USERBOT] Failed to resolve WhatsApp for phone '{normalized_phone}': {e}")
            return None

    async def _get_or_restore_client(self, db: AsyncSession, org_id: uuid.UUID) -> Optional[TelegramClient]:
        client = self.clients.get(org_id)
        if client:
            return client

        bot_record = await self._get_or_create_bot_record(db, org_id)
        if not (bot_record.is_authorized and bot_record.session_string):
            return None

        try:
            client = TelegramClient(
                sessions.StringSession(bot_record.session_string),
                bot_record.api_id,
                bot_record.api_hash,
            )
            await client.connect()
            if await client.is_user_authorized():
                self.clients[org_id] = client
                return client
            logger.warning(f"[USERBOT] Session invalid for org {org_id}")
            return None
        except Exception as e:
            logger.error(f"[USERBOT] Failed to restore User Bot session for org {org_id}: {e}")
            return None

    @staticmethod
    def _normalize_phone(phone: str) -> Optional[str]:
        digits = re.sub(r"\D", "", phone or "")
        if not digits:
            return None
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        if len(digits) == 10:
            digits = "7" + digits
        if len(digits) < 10:
            return None
        return f"+{digits}"

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
