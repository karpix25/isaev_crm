"""
Lead handler for processing messages from potential clients.
Integrates AI-powered lead qualification using OpenRouter API.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
import uuid
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandObject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot import dp, bot
from src.database import AsyncSessionLocal
from src.models.lead import LeadStatus
from src.services.lead_service import lead_service
from src.services.chat_service import chat_service
from src.services.openrouter_service import openrouter_service
from src.services.prompt_service import prompt_service
from src.services.knowledge_service import knowledge_service
from src.services.prompts import SALES_AGENT_SYSTEM_PROMPT, IDENTITY_GUARDRAILS, get_initial_message, build_system_prompt, normalize_system_prompt_template
from src.services.business_hours import is_business_hours, get_business_now
from src.config import settings
from src.bot.utils import get_default_org_id, download_user_avatar
from src.models import AuthSession, OperatorAccessRequest, OperatorAccessRequestStatus, Organization, User
from src.models.user import UserRole

logger = logging.getLogger(__name__)

# Create router for lead handlers
router = Router()

# Debouncing state: {telegram_id: (task, [messages], original_message, has_voice)}
pending_updates = {}

AUTH_SESSION_TTL_SECONDS = 5 * 60


def _normalize_username(username: str | None) -> str | None:
    return (username or "").replace("@", "").strip() or None


def _build_crm_login_url() -> str:
    explicit_url = (getattr(settings, "crm_login_url", "") or "").strip()
    if explicit_url:
        return explicit_url
    origins = settings.cors_origins_list
    if origins:
        base_url = origins[0].rstrip("/")
        if base_url.endswith("/login"):
            return base_url
        return f"{base_url}/login"
    return "/login"


async def _resolve_operator_request_org(db: AsyncSession) -> Organization | None:
    result = await db.execute(
        select(Organization)
        .order_by(Organization.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_latest_operator_access_request(
    db: AsyncSession,
    org_id,
    telegram_id: int,
) -> OperatorAccessRequest | None:
    result = await db.execute(
        select(OperatorAccessRequest)
        .where(
            OperatorAccessRequest.org_id == org_id,
            OperatorAccessRequest.telegram_id == telegram_id,
        )
        .order_by(OperatorAccessRequest.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_or_create_operator_access_request(
    db: AsyncSession,
    org_id,
    telegram_id: int,
    full_name: str | None = None,
    username: str | None = None,
) -> tuple[OperatorAccessRequest, bool]:
    request = await _get_latest_operator_access_request(db, org_id=org_id, telegram_id=telegram_id)
    normalized_username = _normalize_username(username)
    if request:
        changed = False
        next_full_name = (full_name or "").strip() or request.full_name
        if next_full_name != request.full_name:
            request.full_name = next_full_name
            changed = True
        next_username = normalized_username or request.username
        if next_username != request.username:
            request.username = next_username
            changed = True
        if changed:
            await db.flush()
        return request, False

    request = OperatorAccessRequest(
        org_id=org_id,
        telegram_id=telegram_id,
        full_name=(full_name or "").strip() or None,
        username=normalized_username,
        status=OperatorAccessRequestStatus.PENDING.value,
    )
    db.add(request)
    await db.flush()
    return request, True


def _build_operator_access_keyboard(request_id: uuid.UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"operator_access:approve:{request_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"operator_access:reject:{request_id}"),
            ]
        ]
    )


async def _notify_admins_about_operator_request(db: AsyncSession, access_request: OperatorAccessRequest) -> None:
    if not bot:
        return

    result = await db.execute(
        select(User)
        .where(
            User.org_id == access_request.org_id,
            User.role == UserRole.ADMIN,
            User.telegram_id.is_not(None),
        )
    )
    admins = result.scalars().all()
    if not admins:
        logger.warning("No Telegram admins found for operator access request %s", access_request.id)
        return

    applicant_name = (access_request.full_name or "").strip() or "Без имени"
    applicant_username = f"@{access_request.username}" if access_request.username else "—"
    message_text = (
        "🔐 Новая заявка на доступ в CRM\n\n"
        f"Имя: {applicant_name}\n"
        f"Username: {applicant_username}\n"
        f"Telegram ID: {access_request.telegram_id}\n\n"
        "Выберите действие:"
    )
    keyboard = _build_operator_access_keyboard(access_request.id)

    for admin in admins:
        try:
            await bot.send_message(
                chat_id=admin.telegram_id,
                text=message_text,
                reply_markup=keyboard,
            )
        except Exception as exc:
            logger.warning(
                "Failed to send operator request %s notification to admin %s: %s",
                access_request.id,
                admin.telegram_id,
                exc,
            )


async def _notify_operator_access_approved(telegram_id: int) -> None:
    if not bot:
        return
    try:
        login_url = _build_crm_login_url()
        message_text = (
            "✅ Доступ в CRM одобрен администратором.\n"
            f"Войдите по ссылке: {login_url}"
        )
        await bot.send_message(chat_id=telegram_id, text=message_text)
    except Exception as exc:
        logger.warning("Failed to send approval notification to operator %s: %s", telegram_id, exc)


async def _notify_operator_access_rejected(telegram_id: int, reason: str | None = None) -> None:
    if not bot:
        return
    try:
        base_reason = (reason or "").strip() or "Заявка отклонена администратором."
        await bot.send_message(
            chat_id=telegram_id,
            text=f"❌ Доступ в CRM не одобрен.\n{base_reason}",
        )
    except Exception as exc:
        logger.warning("Failed to send rejection notification to operator %s: %s", telegram_id, exc)


async def _try_authorize_login_payload(message: Message, payload: str | None) -> bool:
    """
    Handle admin web login deep-link payload: login_<session_uuid>.
    Returns True when payload was recognized and processed.
    """
    try:
        if not payload or not payload.startswith("login_"):
            return False

        if not message.from_user:
            await message.answer("Не удалось определить пользователя Telegram. Попробуйте ещё раз.")
            return True

        if message.chat and getattr(message.chat, "type", None) != "private":
            await message.answer("Напишите боту в личные сообщения для входа в CRM.")
            return True

        session_id_str = payload.removeprefix("login_")
        try:
            session_uuid = uuid.UUID(session_id_str)
        except Exception:
            await message.answer("Ссылка для входа недействительна. Откройте страницу входа на сайте ещё раз.")
            return True

        async with AsyncSessionLocal() as db:
            res = await db.execute(select(AuthSession).where(AuthSession.id == session_uuid))
            session = res.scalar_one_or_none()
            if not session or session.status != "pending":
                await message.answer("Срок действия сессии истёк. Откройте страницу входа на сайте ещё раз.")
                return True

            now = datetime.now(timezone.utc)
            created_at = session.created_at or now
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            else:
                created_at = created_at.astimezone(timezone.utc)

            if now - created_at > timedelta(seconds=AUTH_SESSION_TTL_SECONDS):
                await db.delete(session)
                await db.commit()
                await message.answer("Срок действия сессии истёк. Откройте страницу входа на сайте ещё раз.")
                return True

            session.telegram_id = message.from_user.id
            session.username = message.from_user.username
            session.full_name = message.from_user.full_name

            user_result = await db.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = user_result.scalar_one_or_none()
            if user:
                session.status = "authorized"
                await db.commit()
                await message.answer("✅ Вход подтверждён. Вернитесь на сайт — авторизация выполнится автоматически.")
                return True

            count_result = await db.execute(select(func.count(User.id)))
            total_users = count_result.scalar() or 0
            if total_users == 0:
                session.status = "authorized"
                await db.commit()
                await message.answer(
                    "✅ Вход подтверждён.\n"
                    "Вы будете первым администратором CRM. Вернитесь на сайт — вход выполнится автоматически."
                )
                return True

            organization = await _resolve_operator_request_org(db)
            if not organization:
                await db.delete(session)
                await db.commit()
                await message.answer("Организация не найдена. Обратитесь к администратору.")
                return True

            access_request, created = await _get_or_create_operator_access_request(
                db=db,
                org_id=organization.id,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username,
            )

            if access_request.status == OperatorAccessRequestStatus.REJECTED.value:
                session.status = "rejected"
                await db.commit()
                await message.answer(
                    "❌ Заявка на доступ отклонена.\n"
                    f"{access_request.rejection_reason or 'Обратитесь к администратору CRM.'}"
                )
                return True

            if access_request.status == OperatorAccessRequestStatus.APPROVED.value:
                session.status = "authorized"
                await db.commit()
                await message.answer("✅ Доступ уже одобрен. Вернитесь на сайт — вход выполнится автоматически.")
                return True

            session.status = "pending_approval"
            await db.commit()

            await message.answer("⏳ Заявка отправлена администратору. Ожидайте одобрения.")
            if created:
                await _notify_admins_about_operator_request(db, access_request)
            return True
    except Exception as e:
        logger.error("Failed to handle login_ payload: %s", e, exc_info=True)
        await message.answer("Произошла ошибка при подтверждении входа. Попробуйте ещё раз.")
        return True

    return False


async def _handle_regular_start(message: Message) -> None:
    """
    Handle regular /start command from potential leads.
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
        
        # Get company name from org settings
        from src.models.organization import Organization
        from sqlalchemy import select
        org_result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = org_result.scalar_one_or_none()
        company_name = org.name if org else "наша компания"

        welcome_text = config.welcome_message if config and config.welcome_message else get_initial_message(company_name)
        if not is_business_hours():
            logger.info(
                "Outside business hours at %s, sending /start out-of-hours notice for lead %s",
                get_business_now().isoformat(),
                lead.id
            )
            welcome_text = (
                f"{welcome_text}\n\n"
                "Сейчас мы не на связи. Ответим в рабочее время."
            )
        
        # Save AI response to database
        sent_message = await message.answer(welcome_text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=welcome_text,
            telegram_message_id=sent_message.message_id,
            sender_name="AI"
        )


@router.message(CommandStart(deep_link=True))
async def cmd_start_deep_link(message: Message, command: CommandObject):
    """
    Handle deep-link /start payloads like /start login_<session_id>.
    """
    payload = (command.args or "").strip()
    handled = await _try_authorize_login_payload(message, payload)
    if handled:
        return
    await _handle_regular_start(message)


@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Handle plain /start.
    """
    await _handle_regular_start(message)

# Fallback: user may send payload as plain message if Telegram doesn't re-trigger /start.
@router.message(F.text.regexp(r"^login_[0-9a-fA-F-]{36}$"))
async def login_payload_fallback(message: Message):
    payload = (message.text or "").strip()
    handled = await _try_authorize_login_payload(message, payload)
    if handled:
        return


@router.callback_query(F.data.regexp(r"^operator_access:(approve|reject):[0-9a-fA-F-]{36}$"))
async def operator_access_callback(query: CallbackQuery):
    if not query.data or not query.from_user:
        await query.answer("Некорректный запрос", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer("Некорректный формат запроса", show_alert=True)
        return

    action = parts[1]
    try:
        request_id = uuid.UUID(parts[2])
    except Exception:
        await query.answer("Некорректный идентификатор заявки", show_alert=True)
        return

    async with AsyncSessionLocal() as db:
        request_result = await db.execute(select(OperatorAccessRequest).where(OperatorAccessRequest.id == request_id))
        access_request = request_result.scalar_one_or_none()
        if not access_request:
            await query.answer("Заявка не найдена", show_alert=True)
            return

        admin_result = await db.execute(select(User).where(User.telegram_id == query.from_user.id))
        admin_user = admin_result.scalar_one_or_none()
        if (
            not admin_user
            or admin_user.role != UserRole.ADMIN
            or str(admin_user.org_id) != str(access_request.org_id)
        ):
            await query.answer("Недостаточно прав", show_alert=True)
            return

        if access_request.status != OperatorAccessRequestStatus.PENDING.value:
            await query.answer("Заявка уже обработана")
            return

        if action == "approve":
            user_result = await db.execute(select(User).where(User.telegram_id == access_request.telegram_id))
            operator = user_result.scalar_one_or_none()
            if operator and str(operator.org_id) != str(access_request.org_id):
                await query.answer("Пользователь привязан к другой организации", show_alert=True)
                return
            if operator and operator.role == UserRole.ADMIN:
                await query.answer("Нельзя изменять роль ADMIN", show_alert=True)
                return

            if operator is None:
                operator = User(
                    org_id=access_request.org_id,
                    telegram_id=access_request.telegram_id,
                    full_name=(access_request.full_name or "").strip() or None,
                    username=_normalize_username(access_request.username),
                    role=UserRole.MANAGER,
                )
                db.add(operator)
            else:
                operator.role = UserRole.MANAGER
                if not operator.full_name and access_request.full_name:
                    operator.full_name = (access_request.full_name or "").strip() or None
                if not operator.username and access_request.username:
                    operator.username = _normalize_username(access_request.username)

            access_request.status = OperatorAccessRequestStatus.APPROVED.value
            access_request.processed_by_user_id = admin_user.id
            access_request.processed_at = datetime.now(timezone.utc)
            access_request.rejection_reason = None
            await db.commit()

            await query.answer("Заявка одобрена")
            if query.message:
                applicant_name = (access_request.full_name or "").strip() or "Без имени"
                try:
                    await query.message.edit_text(
                        "✅ Заявка одобрена\n\n"
                        f"Имя: {applicant_name}\n"
                        f"Telegram ID: {access_request.telegram_id}\n"
                        f"Одобрил: {admin_user.full_name or admin_user.username or admin_user.email or 'Администратор'}"
                    )
                except Exception:
                    pass

            await _notify_operator_access_approved(access_request.telegram_id)
            return

        access_request.status = OperatorAccessRequestStatus.REJECTED.value
        access_request.processed_by_user_id = admin_user.id
        access_request.processed_at = datetime.now(timezone.utc)
        access_request.rejection_reason = "Отклонено администратором."
        await db.commit()

        await query.answer("Заявка отклонена")
        if query.message:
            applicant_name = (access_request.full_name or "").strip() or "Без имени"
            try:
                await query.message.edit_text(
                    "❌ Заявка отклонена\n\n"
                    f"Имя: {applicant_name}\n"
                    f"Telegram ID: {access_request.telegram_id}\n"
                    f"Отклонил: {admin_user.full_name or admin_user.username or admin_user.email or 'Администратор'}"
                )
            except Exception:
                pass

        await _notify_operator_access_rejected(access_request.telegram_id, access_request.rejection_reason)


@router.message(F.text)
async def handle_lead_message(message: Message):
    """
    Handle text messages from leads with debouncing.
    Groups messages sent within 5 seconds into a single AI request.
    """
    user_id = message.from_user.id
    is_voice = getattr(message, "is_voice", False)
    
    # Add message to pending list
    if user_id in pending_updates:
        task, msgs, saved_message, has_voice = pending_updates[user_id]
        task.cancel() # Cancel previous timer
        msgs.append(message.text)
        has_voice = has_voice or is_voice
    else:
        msgs = [message.text]
        saved_message = message
        has_voice = is_voice
    
    # Start new timer task
    task = asyncio.create_task(process_debounced_message(user_id))
    pending_updates[user_id] = (task, msgs, saved_message, has_voice)

async def process_debounced_message(user_id: int):
    """Wait for quiet period and then process all accumulated messages."""
    await asyncio.sleep(5.0) # 5 second window
    
    if user_id not in pending_updates:
        return
        
    _, msgs, message, has_voice = pending_updates.pop(user_id)
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
        metadata = {"is_voice": True} if has_voice else None
        
        await chat_service.save_incoming_message(
            db=db,
            lead_id=lead.id,
            content=combined_text,
            telegram_message_id=message.message_id,
            sender_name=message.from_user.full_name,
            ai_metadata=metadata
        )

        if not is_business_hours():
            logger.info(
                "Outside business hours at %s, skipping bot reply for lead %s",
                get_business_now().isoformat(),
                lead.id
            )
            return
        
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
                text_content = msg.content
                
                # Tell AI if the user sent a voice message
                if msg.ai_metadata and msg.ai_metadata.get("is_voice"):
                    text_content = f"[Голосовое сообщение] {text_content}"
                    
                conversation.append({
                    "role": role,
                    "content": text_content
                })
            
            # Get active prompt configuration
            config = await prompt_service.get_active_config(db, org_id)
            
            # Get company name for prompt injection
            from src.models.organization import Organization
            from sqlalchemy import select
            org_result = await db.execute(select(Organization).where(Organization.id == org_id))
            org = org_result.scalar_one_or_none()
            company_name = org.name if org else "наша компания"
            
            if config and config.system_prompt:
                base_prompt = config.system_prompt
                if "{company_name}" in base_prompt:
                    base_prompt = base_prompt.replace("{company_name}", company_name)
                
                from src.services.custom_field_service import enrich_system_prompt
                system_prompt = await enrich_system_prompt(db, org_id, base_prompt)
            else:
                system_prompt = await build_system_prompt(db, org_id, company_name)
            
            # Technical constraints to prevent breakage
            system_prompt = normalize_system_prompt_template(system_prompt)
            technical_rules = "\n\nCRITICAL: Always respond in valid JSON format. If you need to speak to the user, put your text in the \"message\" field of the JSON."
            identity_rules = IDENTITY_GUARDRAILS.format(company_name=company_name)
            system_prompt = f"{system_prompt}\n\n{identity_rules}{technical_rules}"
            
            # Perform RAG (Retrieval)
            trace_id = f"lead_{lead.id}_{len(messages)}" # Unique per turn
            relevant_docs = await knowledge_service.search_knowledge(
                db=db,
                org_id=org_id,
                query=combined_text,
                limit=3,
                lead_id=lead.id,
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
            response_text = openrouter_service.enforce_identity_answer(
                user_message=combined_text,
                ai_text=ai_response["text"],
                company_name=company_name
            )
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
                    
                # A/B/C Readiness Score
                readiness_score = extracted_data.get("readiness_score")
                if readiness_score in ["A", "B", "C"]:
                    update_fields["readiness_score"] = readiness_score
                
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
                    
                    logger.info("🔥 HOT LEAD: %s (%s) - Ready for handoff!", lead.full_name, lead.telegram_id)
                    
                    # Notify manager via Telegram if MANAGER_TELEGRAM_ID is configured
                    manager_id = getattr(settings, 'manager_telegram_id', None)
                    if manager_id and bot:
                        try:
                            lead_info = (
                                f"🔥 *Горячий лид!*\n"
                                f"👤 Имя: {lead.full_name or 'Неизвестно'}\n"
                                f"📱 Telegram: @{lead.username or lead.telegram_id}\n"
                                f"📞 Телефон: {lead.phone or 'не указан'}\n"
                                f"📊 Статус: {lead.status}\n"
                                f"💬 Данные: {extracted_data.get('budget', 'нет')} | {extracted_data.get('area_sqm', 'нет')} м²"
                            )
                            await bot.send_message(
                                chat_id=manager_id,
                                text=lead_info,
                                parse_mode="Markdown"
                            )
                        except Exception as notify_err:
                            logger.warning("Failed to notify manager: %s", notify_err)
                    
                    # Send handoff message to user
                    await message.answer(
                        "Отлично! Я передал вашу заявку нашему менеджеру. "
                        "Он свяжется с вами в ближайшее время для уточнения деталей. 📞"
                    )
        
        except Exception as e:
            logger.error("Error in AI handler for user %s: %s", user_id, e, exc_info=True)
            # Send user-facing error message instead of silently failing
            try:
                await message.answer(
                    "Извините, произошла техническая ошибка. "
                    "Попробуйте написать снова или свяжитесь с нами напрямую."
                )
            except Exception:
                pass  # If even sending error message fails, just log it


@router.message(F.voice | F.audio | F.video_note)
async def handle_lead_voice(message: Message):
    """
    Handle voice messages from leads.
    Downloads the file, transcribes it via AssemblyAI, and passes text to AI silently.
    """
    import os
    import tempfile
    from src.services.voice_service import voice_service
    
    try:
        # Determine file type and get file ID
        if message.voice:
            file_id = message.voice.file_id
        elif message.audio:
            file_id = message.audio.file_id
        else:
            file_id = message.video_note.file_id
            
        file_info = await bot.get_file(file_id)
        
        # Download file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
            temp_path = temp_file.name
            
        await bot.download_file(file_info.file_path, destination=temp_path)
        
        # Transcribe using service
        transcript = await voice_service.transcribe_audio(temp_path)
        
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        if not transcript:
            # If transcription fails, the bot doesn't know what to say. 
            # We can log it, but we shouldn't reveal it's a bot.
            # Best is to do nothing, or perhaps say something generic via AI later, but right now just return.
            logger.warning(f"Failed to transcribe voice from user {message.from_user.id}")
            return
            
        # Forward the transcribed text to the main AI handler by modifying the message object
        message.text = transcript
        message.is_voice = True
        await handle_lead_message(message)
        
    except Exception as e:
        logger.error(f"Error handling voice message: {e}", exc_info=True)



@router.message(F.photo)
async def handle_lead_photo(message: Message):
    """
    Handle photo messages from leads.
    Downloads the photo and sends it to AI via vision API so AI can actually see the image.
    """
    import base64
    import tempfile
    import os
    from src.models import MessageDirection
    
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
        
        # Save incoming message
        caption = message.caption or ""
        content_for_db = f"[Фото] {caption}" if caption else "[Фото]"
        
        await chat_service.save_incoming_message(
            db=db,
            lead_id=lead.id,
            content=content_for_db,
            telegram_message_id=message.message_id,
            media_url=f"tg://photo/{photo.file_id}",
            sender_name=message.from_user.full_name
        )
        
        # Download photo and convert to base64
        image_base64 = None
        try:
            file_info = await bot.get_file(photo.file_id)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                temp_path = tmp.name
            await bot.download_file(file_info.file_path, destination=temp_path)
            
            with open(temp_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")
            
            os.remove(temp_path)
        except Exception as e:
            logger.error(f"Failed to download photo: {e}", exc_info=True)
        
        # Build system prompt
        config = await prompt_service.get_active_config(db, org_id)

        if not is_business_hours():
            logger.info(
                "Outside business hours at %s, skipping photo reply for lead %s",
                get_business_now().isoformat(),
                lead.id
            )
            return
        
        if config and config.system_prompt:
            base_prompt = config.system_prompt
            if "{company_name}" in base_prompt:
                from src.models.organization import Organization
                from sqlalchemy import select
                org_result = await db.execute(select(Organization).where(Organization.id == org_id))
                org = org_result.scalar_one_or_none()
                company_name = org.name if org else "наша компания"
                base_prompt = base_prompt.replace("{company_name}", company_name)
            
            from src.services.custom_field_service import enrich_system_prompt
            system_prompt = await enrich_system_prompt(db, org_id, base_prompt)
        else:
            from src.models.organization import Organization
            from sqlalchemy import select
            org_result = await db.execute(select(Organization).where(Organization.id == org_id))
            org = org_result.scalar_one_or_none()
            company_name = org.name if org else "наша компания"
            system_prompt = await build_system_prompt(db, org_id, company_name)
        
        system_prompt = normalize_system_prompt_template(system_prompt)
        technical_rules = "\n\nCRITICAL: Always respond in valid JSON format. If you need to speak to the user, put your text in the \"message\" field of the JSON."
        identity_rules = IDENTITY_GUARDRAILS.format(company_name=company_name)
        system_prompt = f"{system_prompt}\n\n{identity_rules}{technical_rules}"
        
        # Get conversation history (exclude the photo message we just saved — it's sent separately via vision)
        history_msgs, _ = await chat_service.get_chat_history(db, lead.id, page_size=20)
        
        formatted_history = []
        for m in reversed(history_msgs):
            # Skip the photo message we just saved (it'll be sent as an image)
            if m.telegram_message_id == message.message_id:
                continue
            role = "user" if m.direction == MessageDirection.INBOUND else "assistant"
            formatted_history.append({"role": role, "content": m.content})
        
        # Generate AI response — use vision if photo downloaded, fallback to text
        try:
            if image_base64:
                ai_response = await openrouter_service.generate_vision_response(
                    conversation_history=formatted_history,
                    system_prompt=system_prompt,
                    image_base64=image_base64,
                    image_caption=caption,
                    model=config.llm_model if config else None
                )
            else:
                # Fallback: tell AI about the photo via text
                formatted_history.append({
                    "role": "user",
                    "content": f"[Клиент прислал фото] {caption}" if caption else "[Клиент прислал фото объекта]"
                })
                ai_response = await openrouter_service.generate_response(
                    formatted_history,
                    system_prompt,
                    model=config.llm_model if config else None
                )
        except Exception as e:
            logger.error(f"Vision API failed, trying text fallback: {e}")
            formatted_history.append({
                "role": "user",
                "content": f"[Клиент прислал фото] {caption}" if caption else "[Клиент прислал фото объекта]"
            })
            ai_response = await openrouter_service.generate_response(
                formatted_history,
                system_prompt,
                model=config.llm_model if config else None
            )
        
        reply_text = ai_response["text"]
        await message.answer(reply_text)
        
        # Extract data and save
        extracted_data = ai_response.get("extracted_data")
        ai_metadata = {"usage": ai_response.get("usage"), "has_vision": bool(image_base64)}
        update_fields = {}
        if extracted_data:
            if extracted_data.get("client_name") and not lead.full_name:
                update_fields["full_name"] = extracted_data.get("client_name")
            if extracted_data.get("phone") and not lead.phone:
                update_fields["phone"] = extracted_data.get("phone")
            
            ai_status = extracted_data.get("status")
            if ai_status and ai_status in [s.value for s in LeadStatus]:
                update_fields["status"] = ai_status
            
            if extracted_data.get("is_hot_lead"):
                update_fields["ai_qualification_status"] = "qualified"
                
            readiness_score = extracted_data.get("readiness_score")
            if readiness_score in ["A", "B", "C"]:
                update_fields["readiness_score"] = readiness_score
            
            update_fields["extracted_data"] = json.dumps(extracted_data, ensure_ascii=False)
        
        await chat_service.send_outbound_message(
            db, lead_id=lead.id, content=reply_text,
            sender_name="AI Agent", ai_metadata=ai_metadata
        )
        
        if update_fields:
            await lead_service.update_lead(db=db, lead_id=lead.id, **update_fields)


# Register router with dispatcher
dp.include_router(router)
