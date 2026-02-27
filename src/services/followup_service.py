"""
Follow-Up Service: sends contextual AI-generated follow-up messages
to leads who haven't responded for a while.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionLocal
from src.models import Lead, LeadStatus, ChatMessage, MessageDirection
from src.services.chat_service import chat_service
from src.services.openrouter_service import openrouter_service
from src.services.prompts import FOLLOWUP_PROMPT

logger = logging.getLogger(__name__)

# Follow-up timing thresholds (hours since last message)
FOLLOWUP_THRESHOLDS = {
    0: 4,    # 1st follow-up: 4 hours after last client message
    1: 24,   # 2nd follow-up: 24 hours after 1st follow-up
    2: 72,   # 3rd follow-up: 72 hours after 2nd follow-up
}

MAX_FOLLOWUPS = 3

# ONLY these statuses should receive follow-ups
# If the lead progressed further (QUALIFIED, MEASUREMENT, etc.) — the deal is moving, no need to nag
FOLLOWUP_STATUSES = {LeadStatus.NEW, LeadStatus.CONSULTING, LeadStatus.FOLLOW_UP}

# How often to run the check (seconds)
CHECK_INTERVAL = 30 * 60  # 30 minutes


async def get_leads_needing_followup(db: AsyncSession) -> list[Lead]:
    """
    Find leads that need a follow-up message.
    
    Criteria:
    - Last message was OUTBOUND (we sent the last message, client didn't reply)
      OR last message was INBOUND but we already started a follow-up sequence
    - Enough time has passed since last activity
    - Status is not WON/LOST/SPAM
    - followup_count < MAX_FOLLOWUPS
    - Has a telegram_id (can receive messages)
    """
    now = datetime.now(timezone.utc)
    
    # Get all active leads with telegram_id
    result = await db.execute(
        select(Lead).where(
            and_(
                Lead.telegram_id.isnot(None),
                Lead.last_message_at.isnot(None),
                Lead.followup_count < MAX_FOLLOWUPS,
                Lead.status.in_(FOLLOWUP_STATUSES),
            )
        )
    )
    leads = result.scalars().all()
    
    eligible = []
    for lead in leads:
        threshold_hours = FOLLOWUP_THRESHOLDS.get(lead.followup_count)
        if threshold_hours is None:
            continue
        
        # Determine the reference time: last_followup_at if we already sent one, 
        # otherwise last_message_at
        if lead.followup_count > 0 and lead.last_followup_at:
            reference_time = lead.last_followup_at
        else:
            reference_time = lead.last_message_at
        
        # Ensure reference_time is timezone-aware
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)
        
        time_since = now - reference_time
        if time_since >= timedelta(hours=threshold_hours):
            # Check that the last message is NOT an inbound message 
            # (if client wrote last and we haven't replied, don't send follow-up,
            #  the AI should have already replied)
            last_msg = await _get_last_message(db, lead.id)
            if last_msg and last_msg.direction == MessageDirection.OUTBOUND:
                eligible.append(lead)
    
    return eligible


async def _get_last_message(db: AsyncSession, lead_id) -> ChatMessage | None:
    """Get the most recent message for a lead."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.lead_id == lead_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def generate_followup_message(db: AsyncSession, lead: Lead) -> str | None:
    """
    Generate a contextual follow-up message using AI based on conversation history.
    Returns the message text, or None if generation fails.
    """
    try:
        # Get recent conversation history
        history_msgs, _ = await chat_service.get_chat_history(db, lead.id, page_size=10)
        
        if not history_msgs:
            return None
        
        # Format history for the prompt
        history_lines = []
        for m in reversed(history_msgs):
            role = "Клиент" if m.direction == MessageDirection.INBOUND else "Менеджер"
            history_lines.append(f"{role}: {m.content}")
        
        conversation_history = "\n".join(history_lines)
        
        # Build follow-up prompt
        prompt = FOLLOWUP_PROMPT.format(
            attempt_number=lead.followup_count + 1,
            conversation_history=conversation_history
        )
        
        # Get org config for model selection
        from src.services.prompt_service import prompt_service
        config = await prompt_service.get_active_config(db, lead.org_id)
        
        # Generate with AI — simple prompt, no JSON parsing needed
        response = await openrouter_service.generate_response(
            conversation_history=[],  # No chat history, everything is in the system prompt
            system_prompt=prompt,
            model=config.llm_model if config else None
        )
        
        text = response.get("text", "").strip()
        
        # Clean up: remove quotes if AI wrapped the message
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1]
        
        return text if text else None
        
    except Exception as e:
        logger.error(f"Failed to generate follow-up for lead {lead.id}: {e}", exc_info=True)
        return None


async def send_followup(db: AsyncSession, lead: Lead, message: str) -> bool:
    """
    Send a follow-up message to the lead via UserBot.
    Returns True if sent successfully.
    """
    from sqlalchemy import update as sql_update
    
    try:
        # Save as outbound message (worker will pick it up due to PENDING status)
        await chat_service.send_outbound_message(
            db,
            lead_id=lead.id,
            content=message,
            sender_name="AI Agent",
            ai_metadata={"type": "followup", "attempt": lead.followup_count + 1}
        )
        
        # Update lead follow-up tracking
        await db.execute(
            sql_update(Lead)
            .where(Lead.id == lead.id)
            .values(
                followup_count=lead.followup_count + 1,
                last_followup_at=datetime.now(timezone.utc)
            )
        )
        await db.commit()
        
        logger.info(
            f"[FOLLOWUP] Sent follow-up #{lead.followup_count + 1} to lead {lead.id} "
            f"(telegram_id={lead.telegram_id}): {message[:50]}..."
        )
        return True
        
    except Exception as e:
        logger.error(f"[FOLLOWUP] Failed to send to lead {lead.id}: {e}", exc_info=True)
        return False


async def check_and_send_followups():
    """
    Main function: check all leads and send follow-ups where needed.
    """
    logger.info("[FOLLOWUP] Running follow-up check...")
    
    async with AsyncSessionLocal() as db:
        try:
            leads = await get_leads_needing_followup(db)
            
            if not leads:
                logger.info("[FOLLOWUP] No leads need follow-up right now.")
                return
            
            logger.info(f"[FOLLOWUP] Found {len(leads)} leads needing follow-up.")
            
            for lead in leads:
                # Generate contextual message
                message = await generate_followup_message(db, lead)
                
                if message:
                    await send_followup(db, lead, message)
                    # Small delay between sends to avoid rate limits
                    await asyncio.sleep(2)
                else:
                    logger.warning(f"[FOLLOWUP] Could not generate message for lead {lead.id}")
                    
        except Exception as e:
            logger.error(f"[FOLLOWUP] Error during follow-up check: {e}", exc_info=True)


async def start_followup_loop():
    """
    Background asyncio loop that periodically checks for leads needing follow-ups.
    Started once at application startup.
    """
    logger.info(f"[FOLLOWUP] Follow-up loop started (check every {CHECK_INTERVAL}s)")
    
    # Wait a bit on startup to let everything initialize
    await asyncio.sleep(30)
    
    while True:
        try:
            await check_and_send_followups()
        except Exception as e:
            logger.error(f"[FOLLOWUP] Unhandled error in follow-up loop: {e}", exc_info=True)
        
        await asyncio.sleep(CHECK_INTERVAL)
