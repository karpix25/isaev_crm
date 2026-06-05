"""
Follow-Up Service: sends contextual AI-generated follow-up messages
to leads who haven't responded for a while.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionLocal
from src.models import Lead, LeadStatus, ChatMessage, MessageDirection
from src.services.chat_service import chat_service
from src.services.lead_stage_context_service import lead_stage_context_service
from src.services.openrouter_service import openrouter_service
from src.services.prompts import FOLLOWUP_PROMPT, STAGE_FOLLOWUP_PROMPT
from src.services.business_hours import is_business_hours, get_business_now

logger = logging.getLogger(__name__)

# Follow-up timing thresholds (hours since last message)
FOLLOWUP_THRESHOLDS = {
    0: 24,   # 1st follow-up: 24 hours after last client message
    1: 72,   # 2nd follow-up: 72 hours after 1st follow-up
    2: 168,  # 3rd follow-up: 7 days after 2nd follow-up
}

MAX_FOLLOWUPS = 3
MAX_FOLLOWUP_AGE_DAYS = 21
AUTO_COOL_AFTER_FINAL_FOLLOWUP = True

# ONLY these statuses should receive follow-ups
# If the lead progressed further (QUALIFIED, MEASUREMENT, etc.) — the deal is moving, no need to nag
FOLLOWUP_STATUSES = {
    LeadStatus.NEW,
    LeadStatus.QUIZ_COMPLETED,
    LeadStatus.MESSENGER_PENDING,
    LeadStatus.DESIGN_PENDING,
    LeadStatus.DESIGN_REVIEW,
    LeadStatus.CONSULTING,
    LeadStatus.QUALIFIED,
    LeadStatus.MEASUREMENT_PENDING,
    LeadStatus.MEASUREMENT_DONE,
    LeadStatus.ESTIMATE_PREPARING,
    LeadStatus.ESTIMATE_REVIEW,
    LeadStatus.ESTIMATE_SENT,
    LeadStatus.ESTIMATE,
    LeadStatus.FOLLOW_UP,
    LeadStatus.CONTRACT_NEGOTIATION,
    LeadStatus.CONTRACT,
    LeadStatus.PAYMENT_PENDING,
    LeadStatus.KEYS_PENDING,
    LeadStatus.READY_TO_START,
}

STAGE_FOLLOWUP_THRESHOLDS = {
    "awaiting_design_project": {0: 3, 1: 24, 2: 72},
    "awaiting_measurement_slot": {0: 3, 1: 24, 2: 72},
    "confirm_measurement": {0: 6, 1: 24, 2: 72},
    "estimate_internal_review": {0: 24, 1: 48, 2: 96},
    "needs_estimate_review": {0: 24, 1: 72, 2: 120},
    "contract_closing": {0: 24, 1: 72, 2: 120},
    "awaiting_payment": {0: 24, 1: 72, 2: 120},
    "awaiting_keys": {0: 24, 1: 72, 2: 120},
    "prepare_project_start": {0: 24, 1: 72, 2: 120},
    "project_in_work": {0: 72, 1: 120, 2: 168},
    "direct_chat_qualification": {0: 3, 1: 24, 2: 72},
    "general_consultation": {0: 24, 1: 72, 2: 168},
}

STAGE_SCENARIOS = {
    "awaiting_design_project": (
        "Ждем дизайн-проект",
        "Спокойно объяснить, что проект поможет посчитать смету без лишних догадок, и предложить прислать файл в удобном виде.",
    ),
    "awaiting_measurement_slot": (
        "Ждем выбор слота замера",
        "Мягко вернуть к бесплатному замеру как к безопасному следующему шагу: без обязательств, чтобы не считать вслепую.",
    ),
    "confirm_measurement": (
        "Ждем подтверждение замера",
        "Аккуратно подтвердить слот и помочь клиенту спокойно завершить подготовку к выезду инженера.",
    ),
    "estimate_internal_review": (
        "Смета на проверке",
        "Если клиент сам написал — спокойно объяснить, что расчет проверяет сметчик, чтобы не отправить сырые цифры.",
    ),
    "needs_estimate_review": (
        "Ждем реакцию на смету",
        "Вернуть клиента к реакции на файл сметы без выдумывания цифр: предложить передать вопросы по расчету менеджеру или сметчику.",
    ),
    "contract_closing": (
        "Ждем финальное решение по договору",
        "Мягко вернуть клиента к фиксации даты старта, бригады или условий договора.",
    ),
    "awaiting_payment": (
        "Ждем оплату",
        "Помочь клиенту завершить оплату и спокойно объяснить, что после нее согласуем передачу ключей или доступ на объект.",
    ),
    "awaiting_keys": (
        "Ждем передачу ключей",
        "Аккуратно вернуть клиента к передаче ключей/доступа: удобная дата, контакт на объекте или способ передачи.",
    ),
    "prepare_project_start": (
        "Ключи получены",
        "Подтвердить подготовку к старту работ: дату, прораба, бригаду или следующий организационный шаг.",
    ),
    "project_in_work": (
        "Объект в работе",
        "Отвечать по делу и при необходимости фиксировать вопрос для менеджера или прораба.",
    ),
    "direct_chat_qualification": (
        "Клиент пишет напрямую",
        "Продолжить диалог и довести до квиза, если данных мало для расчета.",
    ),
    "general_consultation": (
        "Общий прогрев",
        "Коротко и по-человечески вернуть диалог через пользу: расчет, похожий объект, замер или ответ на тревожный вопрос.",
    ),
}

# How often to run the check (seconds)
CHECK_INTERVAL = 30 * 60  # 30 minutes


async def get_leads_needing_followup(db: AsyncSession) -> list[Lead]:
    """
    Find leads that need a follow-up message.
    
    Criteria:
    - Last message was OUTBOUND (we sent the last message, client didn't reply)
    - Enough time has passed since last activity
    - Follow-up window is not older than MAX_FOLLOWUP_AGE_DAYS
    - Status is not WON/LOST/SPAM
    - followup_count < MAX_FOLLOWUPS
    - Has a telegram_id (can receive messages)
    """
    now = datetime.now(timezone.utc)
    
    latest_message_subquery = (
        select(
            ChatMessage.lead_id,
            ChatMessage.direction,
            func.row_number()
            .over(
                partition_by=ChatMessage.lead_id,
                order_by=(ChatMessage.created_at.desc(), ChatMessage.id.desc()),
            )
            .label("row_number"),
        )
        .subquery()
    )

    result = await db.execute(
        select(Lead)
        .join(
            latest_message_subquery,
            and_(
                latest_message_subquery.c.lead_id == Lead.id,
                latest_message_subquery.c.row_number == 1,
                latest_message_subquery.c.direction == MessageDirection.OUTBOUND,
            ),
        )
        .where(
            and_(
                Lead.telegram_id.isnot(None),
                Lead.last_message_at.isnot(None),
                Lead.followup_count < MAX_FOLLOWUPS,
                Lead.status.in_([status.value for status in FOLLOWUP_STATUSES]),
            )
        )
    )
    leads = result.scalars().unique().all()
    
    eligible = []
    for lead in leads:
        if _lead_has_do_not_contact_flag(lead):
            continue
        try:
            scenario_key, _, _ = await _build_stage_context(db, lead)
            setattr(lead, "_stage_context", {"next_action": scenario_key})
        except Exception as exc:
            logger.warning("[FOLLOWUP] Could not build stage context for lead %s: %s", lead.id, exc)

        threshold_hours = _get_threshold_hours(lead)
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

        if _is_followup_too_old(now, reference_time):
            await _cool_down_stale_followup(db, lead, reason="followup_window_expired")
            continue
        
        time_since = now - reference_time
        if time_since >= timedelta(hours=threshold_hours):
            eligible.append(lead)
    
    return eligible


def _lead_has_do_not_contact_flag(lead: Lead) -> bool:
    if not lead.extracted_data:
        return False
    try:
        data = json.loads(lead.extracted_data)
    except json.JSONDecodeError:
        return False
    return bool(isinstance(data, dict) and data.get("do_not_contact"))


def _is_followup_too_old(now: datetime, reference_time: datetime) -> bool:
    return now - reference_time > timedelta(days=MAX_FOLLOWUP_AGE_DAYS)

def _get_threshold_hours(lead: Lead) -> int | None:
    stage_key = _get_stage_key_cached(lead)
    stage_thresholds = STAGE_FOLLOWUP_THRESHOLDS.get(stage_key)
    if stage_thresholds:
        return stage_thresholds.get(lead.followup_count)
    return FOLLOWUP_THRESHOLDS.get(lead.followup_count)


def _get_stage_key_cached(lead: Lead) -> str:
    stage_context = getattr(lead, "_stage_context", None)
    if stage_context:
        return stage_context.get("next_action") or "general_consultation"
    return "general_consultation"


async def _build_stage_context(db: AsyncSession, lead: Lead) -> tuple[str, dict[str, str], str]:
    stage_context = await lead_stage_context_service.build_context(db=db, lead=lead)
    scenario_key = stage_context.next_action if stage_context.next_action in STAGE_SCENARIOS else "general_consultation"
    scenario_title, scenario_goal = STAGE_SCENARIOS.get(scenario_key, STAGE_SCENARIOS["general_consultation"])
    return scenario_key, {"title": scenario_title, "goal": scenario_goal}, stage_context.prompt_block


async def generate_followup_message(db: AsyncSession, lead: Lead) -> tuple[str | None, str | None]:
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
        scenario_key, scenario_meta, stage_context_block = await _build_stage_context(db, lead)

        if scenario_key != "general_consultation":
            prompt = STAGE_FOLLOWUP_PROMPT.format(
                attempt_number=lead.followup_count + 1,
                scenario_title=scenario_meta["title"],
                scenario_goal=scenario_meta["goal"],
                attempt_guidance=_attempt_guidance(lead.followup_count + 1),
                stage_context=stage_context_block,
                conversation_history=conversation_history,
            )
        else:
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
        
        return (text if text else None, scenario_key)
        
    except Exception as e:
        logger.error(f"Failed to generate follow-up for lead {lead.id}: {e}", exc_info=True)
        return None, None


def _attempt_guidance(attempt_number: int) -> str:
    if attempt_number == 1:
        return "Попытка 1: мягкое напоминание, польза для клиента и один ясный следующий шаг."
    if attempt_number == 2:
        return "Попытка 2: убрать оставшуюся неопределенность и предложить конкретное действие без давления."
    return "Попытка 3: финальное теплое касание: предложи продолжить сейчас или поставить вопрос на паузу. Не спорь и не уговаривай."


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
            ai_metadata={
                "type": "followup",
                "attempt": lead.followup_count + 1,
                "followup_variant": getattr(lead, "_followup_variant", None),
            }
        )
        
        # Update lead follow-up tracking
        next_count = lead.followup_count + 1
        update_values = {
            "followup_count": next_count,
            "last_followup_at": datetime.now(timezone.utc),
        }
        if AUTO_COOL_AFTER_FINAL_FOLLOWUP and next_count >= MAX_FOLLOWUPS:
            update_values["status"] = LeadStatus.FOLLOW_UP.value

        await db.execute(
            sql_update(Lead)
            .where(Lead.id == lead.id)
            .values(**update_values)
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


async def _cool_down_stale_followup(db: AsyncSession, lead: Lead, reason: str) -> None:
    from sqlalchemy import update as sql_update

    await db.execute(
        sql_update(Lead)
        .where(Lead.id == lead.id)
        .values(
            followup_count=MAX_FOLLOWUPS,
            status=LeadStatus.FOLLOW_UP.value,
        )
    )
    await db.commit()
    logger.info("[FOLLOWUP] Cooled stale lead %s: %s", lead.id, reason)


async def check_and_send_followups():
    """
    Main function: check all leads and send follow-ups where needed.
    """
    logger.info("[FOLLOWUP] Running follow-up check...")

    if not is_business_hours():
        logger.info("[FOLLOWUP] Outside business hours at %s, skipping sends.", get_business_now().isoformat())
        return
    
    async with AsyncSessionLocal() as db:
        try:
            leads = await get_leads_needing_followup(db)
            
            if not leads:
                logger.info("[FOLLOWUP] No leads need follow-up right now.")
                return
            
            logger.info(f"[FOLLOWUP] Found {len(leads)} leads needing follow-up.")
            
            for lead in leads:
                # Generate contextual message
                message, scenario_key = await generate_followup_message(db, lead)
                
                if message:
                    setattr(lead, "_followup_variant", scenario_key)
                    await send_followup(db, lead, message)
                    # Small delay between sends to avoid rate limits
                    await asyncio.sleep(2)
                else:
                    logger.warning(f"[FOLLOWUP] Could not generate message for lead {lead.id}")
                    
        except Exception as e:
            logger.error(f"[FOLLOWUP] Error during follow-up check: {e}", exc_info=True)


async def start_followup_loop(stop_event: asyncio.Event | None = None):
    """
    Background asyncio loop that periodically checks for leads needing follow-ups.
    Started once at application startup.
    """
    logger.info(f"[FOLLOWUP] Follow-up loop started (check every {CHECK_INTERVAL}s)")
    
    # Wait a bit on startup to let everything initialize
    stop_event = stop_event or asyncio.Event()
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=30)
        return
    except asyncio.TimeoutError:
        pass
    
    while not stop_event.is_set():
        try:
            await check_and_send_followups()
        except Exception as e:
            logger.error(f"[FOLLOWUP] Unhandled error in follow-up loop: {e}", exc_info=True)
        
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CHECK_INTERVAL)
        except asyncio.TimeoutError:
            continue
