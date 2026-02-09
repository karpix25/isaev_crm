"""
Lead handler for processing messages from potential clients.
Integrates AI-powered lead qualification using OpenRouter API.
"""
import asyncio
import json
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot import dp, bot
from src.database import AsyncSessionLocal
from src.models.lead import LeadStatus
from src.services.lead_service import lead_service
from src.services.chat_service import chat_service
from src.services.openrouter_service import openrouter_service
from src.services.prompt_service import prompt_service
from src.services.knowledge_service import knowledge_service
from src.services.prompts import SALES_AGENT_SYSTEM_PROMPT, get_initial_message
from src.config import settings
from src.bot.utils import get_default_org_id, download_user_avatar

# Create router for lead handlers
router = Router()

# Debouncing state: {telegram_id: (task, [messages], original_message)}
pending_updates = {}


@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Handle /start command from potential leads.
    Creates lead if new user and starts AI conversation.
    """
    async with AsyncSessionLocal() as db:
        # Get default organization ID
        org_id = await get_default_org_id(db)
        
        # Get or create lead
        avatar_url = await download_user_avatar(bot, message.from_user.id)
        lead = await lead_service.create_or_get_lead(
            db=db,
            org_id=org_id,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            avatar_url=avatar_url
        )
        
        # Save /start command
        await chat_service.save_incoming_message(
            db=db,
            lead_id=lead.id,
            content=message.text,
            telegram_message_id=message.message_id,
            sender_name=message.from_user.full_name
        )
        
        # Get initial message from database or fallback
        config = await prompt_service.get_active_config(db, org_id)
        welcome_text = config.welcome_message if config and config.welcome_message else get_initial_message()
        
        # Save AI response to database
        sent_message = await message.answer(welcome_text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=welcome_text,
            telegram_message_id=sent_message.message_id,
            sender_name="AI"
        )


@router.message(F.text)
async def handle_lead_message(message: Message):
    """
    Handle text messages from leads with debouncing.
    Groups messages sent within 5 seconds into a single AI request.
    """
    user_id = message.from_user.id
    
    # Add message to pending list
    if user_id in pending_updates:
        task, msgs, _ = pending_updates[user_id]
        task.cancel() # Cancel previous timer
        msgs.append(message.text)
    else:
        msgs = [message.text]
    
    # Start new timer task
    task = asyncio.create_task(process_debounced_message(user_id))
    pending_updates[user_id] = (task, msgs, message)

async def process_debounced_message(user_id: int):
    """Wait for quiet period and then process all accumulated messages."""
    await asyncio.sleep(5.0) # 5 second window
    
    if user_id not in pending_updates:
        return
        
    _, msgs, message = pending_updates.pop(user_id)
    combined_text = " ".join(msgs)
    
    async with AsyncSessionLocal() as db:
        # Get default organization ID
        org_id = await get_default_org_id(db)
        
        # Get or create lead
        lead = await lead_service.create_or_get_lead(
            db=db,
            org_id=org_id,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username
        )
        
        # Save incoming message (using combined text as one entry for AI context)
        await chat_service.save_incoming_message(
            db=db,
            lead_id=lead.id,
            content=combined_text,
            telegram_message_id=message.message_id,
            sender_name=message.from_user.full_name
        )
        
        # Check if AI should handle this lead
        if lead.ai_qualification_status == "handoff_required":
            await message.answer(
                "✅ Спасибо за сообщение! Наш менеджер уже работает с вашим запросом и скоро свяжется с вами."
            )
            return

        try:
            # Get conversation history
            messages, total = await chat_service.get_chat_history(
                db=db,
                lead_id=lead.id,
                page=1,
                page_size=20  # Last 20 messages
            )
            
            # Convert to OpenRouter format
            conversation = []
            for msg in reversed(messages):  # Oldest first (messages are DESC, so reverse)
                role = "user" if msg.direction == "inbound" else "assistant"
                conversation.append({
                    "role": role,
                    "content": msg.content
                })
            
            # Get active prompt configuration
            config = await prompt_service.get_active_config(db, org_id)
            base_prompt = config.system_prompt if config else SALES_AGENT_SYSTEM_PROMPT
            
            # Inject custom fields into prompt
            from src.services.custom_field_service import inject_custom_fields_into_prompt
            enhanced_prompt = await inject_custom_fields_into_prompt(db, org_id, base_prompt)
            
            # Technical constraints to prevent breakage
            technical_rules = "\n\nCRITICAL: Always respond in valid JSON format. If you need to speak to the user, put your text in the \"message\" field of the JSON."
            system_prompt = f"{enhanced_prompt}{technical_rules}"
            
            # Perform RAG (Retrieval)
            trace_id = f"lead_{lead.id}_{len(messages)}" # Unique per turn
            relevant_docs = await knowledge_service.search_knowledge(
                db=db,
                org_id=org_id,
                query=combined_text,
                limit=3,
                embedding_model=config.embedding_model if config else None,
                trace_id=trace_id,
                user_id=str(message.from_user.id)
            )
            
            ai_metadata = {}
            if relevant_docs:
                context_str = "\n\n".join([f"Source: {d.title}\nContent: {d.content}" for d in relevant_docs])
                system_prompt = f"{system_prompt}\n\nRELEVANT KNOWLEDGE:\n{context_str}\n\nUse this context to answer accurately."
                
                # Save context for transparency
                ai_metadata["retrieved_context"] = [
                    {"title": d.title, "content": d.content, "id": str(d.id)}
                    for d in relevant_docs
                ]
            
            # Generate AI response
            ai_response = await openrouter_service.generate_response(
                conversation_history=conversation,
                system_prompt=system_prompt,
                model=config.llm_model if config else None,
                trace_id=trace_id,
                user_id=str(message.from_user.id)
            )
            
            # Send AI response to user
            response_text = ai_response["text"]
            sent_message = await message.answer(response_text)
            
            # Save AI response to database
            await chat_service.send_outbound_message(
                db=db,
                lead_id=lead.id,
                content=response_text,
                telegram_message_id=sent_message.message_id,
                sender_name="AI",
                ai_metadata=ai_metadata
            )
            
            # Update lead with extracted data
            extracted_data = ai_response.get("extracted_data")
            if extracted_data:
                # 1. Sync structured fields if present
                update_fields = {}
                
                # Full Name
                if extracted_data.get("client_name") and not lead.full_name:
                    update_fields["full_name"] = extracted_data.get("client_name")
                
                # Phone
                if extracted_data.get("phone") and not lead.phone:
                    update_fields["phone"] = extracted_data.get("phone")
                
                # Status Change (from AI)
                ai_status = extracted_data.get("status")
                if ai_status and ai_status in [s.value for s in LeadStatus]:
                    update_fields["status"] = ai_status
                
                # Qualification Status
                if extracted_data.get("is_hot_lead"):
                    update_fields["ai_qualification_status"] = "qualified"
                
                # Save extracted data as JSON string
                update_fields["extracted_data"] = json.dumps(extracted_data, ensure_ascii=False)
                
                # Execute update
                if update_fields:
                    await lead_service.update_lead(
                        db=db,
                        lead_id=lead.id,
                        **update_fields
                    )
                
                # Check if handoff is needed
                if openrouter_service.should_handoff(extracted_data):
                    # Update lead status to handoff if not already set by AI
                    if update_fields.get("ai_qualification_status") != "handoff_required":
                        await lead_service.update_lead(
                            db=db,
                            lead_id=lead.id,
                            ai_qualification_status="handoff_required",
                            status=LeadStatus.QUALIFIED
                        )
                    
                    # Notify manager (in future: send notification via admin panel)
                    print(f"🔥 HOT LEAD: {lead.full_name} ({lead.telegram_id}) - Ready for handoff!")
                    
                    # Send handoff message to user
                    await message.answer(
                        "Отлично! Я передал вашу заявку нашему менеджеру. "
                        "Он свяжется с вами в ближайшее время для уточнения деталей. 📞"
                    )
        
        except Exception as e:
            print(f"Error in AI handler: {e}")


@router.message(F.photo)
async def handle_lead_photo(message: Message):
    """
    Handle photo messages from leads.
    """
    # Get photo file_id (largest size)
    photo = message.photo[-1]
    
    async with AsyncSessionLocal() as db:
        # Get default organization ID
        org_id = await get_default_org_id(db)
        
        # Get or create lead
        lead = await lead_service.create_or_get_lead(
            db=db,
            org_id=org_id,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username
        )
        
        # Save message with photo
        caption = message.caption or "[Photo]"
        await chat_service.save_incoming_message(
            db=db,
            lead_id=lead.id,
            content=caption,
            telegram_message_id=message.message_id,
            media_url=f"tg://photo/{photo.file_id}",
            sender_name=message.from_user.full_name
        )
    
    await message.answer("✅ Фото получено! Спасибо за дополнительную информацию.")


# Register router with dispatcher
dp.include_router(router)
