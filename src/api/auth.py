from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import sqlalchemy as sa
import logging
import time
from pydantic import BaseModel
import uuid
from datetime import datetime, timedelta, timezone

from src.database import get_db
from src.models import (
    User,
    Organization,
    AuthSession,
    OperatorAccessRequest,
    OperatorAccessRequestStatus,
)
from src.models.user import UserRole
from src.schemas.auth import TokenResponse
from src.services.auth import auth_service
from src.bot import bot as telegram_bot
from src.config import settings
from src.dependencies.auth import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

class TelegramBotInfoResponse(BaseModel):
    bot_id: int
    username: str | None = None


_telegram_bot_info_cache: TelegramBotInfoResponse | None = None
_telegram_bot_info_cache_expires_at: float = 0.0


@router.get("/telegram/bot", response_model=TelegramBotInfoResponse)
async def telegram_bot_info():
    """
    Returns bot id/username for Telegram.Login.auth (popup flow from telegram-widget.js).
    Cached in-memory to avoid extra Bot API calls.
    """
    global _telegram_bot_info_cache, _telegram_bot_info_cache_expires_at

    if not telegram_bot:
        raise HTTPException(status_code=500, detail="Telegram bot not initialized")

    now = time.time()
    if _telegram_bot_info_cache and now < _telegram_bot_info_cache_expires_at:
        return _telegram_bot_info_cache

    try:
        me = await telegram_bot.get_me()
        _telegram_bot_info_cache = TelegramBotInfoResponse(bot_id=me.id, username=getattr(me, "username", None))
        _telegram_bot_info_cache_expires_at = now + 60 * 60  # 1 hour
        return _telegram_bot_info_cache
    except Exception as e:
        logger.error("Failed to fetch Telegram bot info: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch Telegram bot info")


class TelegramBotInitResponse(BaseModel):
    session_id: str
    bot_username: str
    expires_in: int


class TelegramBotCheckResponse(BaseModel):
    status: str  # pending | pending_approval | rejected | authorized | expired
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    detail: str | None = None


AUTH_SESSION_TTL_SECONDS = 5 * 60


class TelegramWebhookInfoResponse(BaseModel):
    mode: str
    configured_url: str
    current_url: str
    pending_update_count: int | None = None
    last_error_message: str | None = None
    last_error_date: int | None = None


class OperatorUserResponse(BaseModel):
    id: uuid.UUID
    telegram_id: int | None = None
    full_name: str | None = None
    username: str | None = None
    phone: str | None = None
    email: str | None = None
    role: UserRole

    class Config:
        from_attributes = True


class OperatorCreateRequest(BaseModel):
    telegram_id: int
    full_name: str | None = None
    username: str | None = None
    phone: str | None = None
    email: str | None = None
    role: UserRole = UserRole.MANAGER


class OperatorUpdateRequest(BaseModel):
    full_name: str | None = None
    username: str | None = None
    phone: str | None = None
    email: str | None = None
    role: UserRole | None = None


class OperatorAccessRequestResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    telegram_id: int
    full_name: str | None = None
    username: str | None = None
    status: str
    processed_by_user_id: uuid.UUID | None = None
    processed_by_name: str | None = None
    processed_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime


class OperatorAccessApproveRequest(BaseModel):
    role: UserRole = UserRole.MANAGER
    full_name: str | None = None
    username: str | None = None
    phone: str | None = None
    email: str | None = None


class OperatorAccessRejectRequest(BaseModel):
    reason: str | None = None


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
    org_id: uuid.UUID,
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
    org_id: uuid.UUID,
    telegram_id: int,
    full_name: str | None = None,
    username: str | None = None,
) -> OperatorAccessRequest:
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
            await db.commit()
            await db.refresh(request)
        return request

    request = OperatorAccessRequest(
        org_id=org_id,
        telegram_id=telegram_id,
        full_name=(full_name or "").strip() or None,
        username=normalized_username,
        status=OperatorAccessRequestStatus.PENDING.value,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


def _telegram_mode() -> str:
    mode = (settings.telegram_update_mode or "").strip().lower()
    if mode not in {"polling", "webhook", "auto"}:
        return "polling"
    return mode


async def _ensure_telegram_webhook() -> TelegramWebhookInfoResponse:
    """
    Ensure Telegram webhook is configured to TELEGRAM_WEBHOOK_URL.
    If webhook is missing/mismatched, reset it before login flow starts.
    """
    if not telegram_bot:
        raise HTTPException(status_code=500, detail="Telegram bot not initialized")
    mode = _telegram_mode()
    configured_url = settings.telegram_webhook_url

    if mode == "polling":
        info = await telegram_bot.get_webhook_info()
        return TelegramWebhookInfoResponse(
            mode=mode,
            configured_url=configured_url,
            current_url=getattr(info, "url", "") or "",
            pending_update_count=getattr(info, "pending_update_count", None),
            last_error_message=getattr(info, "last_error_message", None),
            last_error_date=getattr(info, "last_error_date", None),
        )
    if not configured_url:
        raise HTTPException(status_code=503, detail="TELEGRAM_WEBHOOK_URL is empty for webhook mode.")

    info = await telegram_bot.get_webhook_info()
    current_url = getattr(info, "url", "") or ""

    if current_url != configured_url:
        logger.warning(
            "Webhook mismatch detected. current=%s configured=%s. Re-setting webhook.",
            current_url,
            configured_url,
        )
        await telegram_bot.set_webhook(configured_url, drop_pending_updates=False)
        info = await telegram_bot.get_webhook_info()
        current_url = getattr(info, "url", "") or ""

    return TelegramWebhookInfoResponse(
        mode=mode,
        configured_url=configured_url,
        current_url=current_url,
        pending_update_count=getattr(info, "pending_update_count", None),
        last_error_message=getattr(info, "last_error_message", None),
        last_error_date=getattr(info, "last_error_date", None),
    )


@router.get("/telegram/bot/webhook-info", response_model=TelegramWebhookInfoResponse)
async def telegram_bot_webhook_info():
    return await _ensure_telegram_webhook()


@router.post("/telegram/bot/init", response_model=TelegramBotInitResponse)
async def telegram_bot_login_init(db: AsyncSession = Depends(get_db)):
    """
    Creates a one-time auth session and returns bot deep-link parameters.
    """
    webhook_info = await _ensure_telegram_webhook()
    if webhook_info.mode == "webhook" and webhook_info.current_url != webhook_info.configured_url:
        raise HTTPException(status_code=503, detail="Telegram webhook is not configured correctly. Please try again shortly.")

    info = await telegram_bot_info()
    if not info.username:
        raise HTTPException(status_code=500, detail="Telegram bot has no username")

    session = AuthSession(
        id=uuid.uuid4(),
        status="pending",
    )
    db.add(session)
    await db.commit()

    return TelegramBotInitResponse(
        session_id=str(session.id),
        bot_username=info.username,
        expires_in=AUTH_SESSION_TTL_SECONDS,
    )


@router.get("/telegram/bot/check/{session_id}", response_model=TelegramBotCheckResponse)
async def telegram_bot_login_check(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Poll endpoint: once bot marks session authorized, returns JWT tokens and consumes the session.
    """
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        return TelegramBotCheckResponse(status="expired")

    result = await db.execute(select(AuthSession).where(AuthSession.id == sid))
    session = result.scalar_one_or_none()
    if not session:
        return TelegramBotCheckResponse(status="expired")

    # Expire old sessions
    now = datetime.now(timezone.utc)
    created_at = session.created_at or now
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    else:
        created_at = created_at.astimezone(timezone.utc)

    if now - created_at > timedelta(seconds=AUTH_SESSION_TTL_SECONDS):
        await db.delete(session)
        await db.commit()
        return TelegramBotCheckResponse(status="expired")

    if not session.telegram_id:
        return TelegramBotCheckResponse(status="pending")

    telegram_id = int(session.telegram_id)

    if session.status == "pending_approval":
        organization = await _resolve_operator_request_org(db)
        if not organization:
            return TelegramBotCheckResponse(
                status="pending_approval",
                detail="Заявка на доступ ожидает администратора.",
            )

        access_request = await _get_latest_operator_access_request(
            db,
            org_id=organization.id,
            telegram_id=telegram_id,
        )

        if access_request:
            if access_request.status == OperatorAccessRequestStatus.REJECTED.value:
                session.status = "rejected"
                await db.commit()
                return TelegramBotCheckResponse(
                    status="rejected",
                    detail=access_request.rejection_reason or "Заявка на доступ отклонена администратором.",
                )
            if access_request.status == OperatorAccessRequestStatus.APPROVED.value:
                session.status = "authorized"
                await db.commit()
            else:
                return TelegramBotCheckResponse(
                    status="pending_approval",
                    detail="Заявка отправлена администратору. Ожидайте одобрения.",
                )
        else:
            return TelegramBotCheckResponse(
                status="pending_approval",
                detail="Заявка отправлена администратору. Ожидайте одобрения.",
            )

    if session.status == "rejected":
        organization = await _resolve_operator_request_org(db)
        if organization:
            access_request = await _get_latest_operator_access_request(
                db,
                org_id=organization.id,
                telegram_id=telegram_id,
            )
            if access_request and access_request.status == OperatorAccessRequestStatus.APPROVED.value:
                session.status = "authorized"
                await db.commit()
            elif access_request and access_request.status == OperatorAccessRequestStatus.REJECTED.value:
                return TelegramBotCheckResponse(
                    status="rejected",
                    detail=access_request.rejection_reason or "Заявка на доступ отклонена администратором.",
                )

        if session.status == "rejected":
            return TelegramBotCheckResponse(
                status="rejected",
                detail="Заявка на доступ отклонена администратором.",
            )

    if session.status != "authorized":
        return TelegramBotCheckResponse(status="pending")
    user_result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = user_result.scalar_one_or_none()

    if not user:
        count_result = await db.execute(select(sa.func.count(User.id)))
        total_users = count_result.scalar() or 0

        if total_users == 0:
            user = await _get_or_create_user_by_telegram(
                db=db,
                telegram_id=telegram_id,
                full_name=session.full_name,
                username=session.username,
            )
        else:
            organization = await _resolve_operator_request_org(db)
            if not organization:
                return TelegramBotCheckResponse(
                    status="expired",
                    detail="Организация не найдена. Обратитесь к администратору.",
                )

            access_request = await _get_or_create_operator_access_request(
                db=db,
                org_id=organization.id,
                telegram_id=telegram_id,
                full_name=session.full_name,
                username=session.username,
            )

            if access_request.status == OperatorAccessRequestStatus.REJECTED.value:
                session.status = "rejected"
                await db.commit()
                return TelegramBotCheckResponse(
                    status="rejected",
                    detail=access_request.rejection_reason or "Заявка на доступ отклонена администратором.",
                )

            if access_request.status != OperatorAccessRequestStatus.APPROVED.value:
                session.status = "pending_approval"
                await db.commit()
                return TelegramBotCheckResponse(
                    status="pending_approval",
                    detail="Заявка отправлена администратору. Ожидайте одобрения.",
                )

            user_result = await db.execute(select(User).where(User.telegram_id == telegram_id))
            user = user_result.scalar_one_or_none()
            if not user:
                user = User(
                    org_id=organization.id,
                    telegram_id=telegram_id,
                    role=UserRole.MANAGER,
                    full_name=(session.full_name or "").strip() or access_request.full_name,
                    username=_normalize_username(session.username) or access_request.username,
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)

    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})

    await db.delete(session)
    await db.commit()

    return TelegramBotCheckResponse(
        status="authorized",
        access_token=access_token,
        refresh_token=refresh_token,
    )

async def _get_or_create_user_by_telegram(
    db: AsyncSession,
    telegram_id: int,
    full_name: str | None = None,
    username: str | None = None,
) -> User:
    normalized_username = _normalize_username(username)

    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user:
        changed = False
        if full_name and full_name != user.full_name:
            user.full_name = full_name
            changed = True
        if normalized_username and normalized_username != user.username:
            user.username = normalized_username
            changed = True
        if changed:
            await db.commit()
            await db.refresh(user)
        return user

    # Check if database is completely empty (0 users)
    count_result = await db.execute(select(sa.func.count(User.id)))
    total_users = count_result.scalar() or 0

    if total_users != 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found. Please contact administrator.",
        )

    logger.info("Initializing empty database with first Telegram Admin!")

    # Create a default organization since none exists
    organization = Organization(name="Default Organization")
    db.add(organization)
    await db.flush()  # to get organization.id

    # Create the admin user
    user = User(
        org_id=organization.id,
        telegram_id=telegram_id,
        role=UserRole.ADMIN,
        full_name=full_name,
        username=normalized_username,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/telegram", response_model=TokenResponse)
async def telegram_auth(
    auth_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Telegram widget authentication.
    Bootstraps the first user as ADMIN if the database is empty.
    """
    # Validate Telegram auth data from widget
    if not auth_service.validate_telegram_widget_auth(auth_data.copy()):
        # Try Mini App validation as fallback just in case
        if not auth_service.validate_telegram_auth(auth_data.copy()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram authentication data"
            )
    
    telegram_id = auth_data.get("id")
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No telegram_id provided"
        )

    user = await _get_or_create_user_by_telegram(
        db=db,
        telegram_id=int(telegram_id),
        full_name=" ".join(
            [p for p in [auth_data.get("first_name"), auth_data.get("last_name")] if p]
        )
        or None,
        username=auth_data.get("username"),
    )
    
    # Create tokens
    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.get("/operator-access-requests", response_model=list[OperatorAccessRequestResponse])
async def list_operator_access_requests(
    status_filter: str = Query("pending", pattern="^(pending|approved|rejected|all)$"),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            OperatorAccessRequest,
            User.full_name,
            User.username,
            User.email,
        )
        .outerjoin(User, OperatorAccessRequest.processed_by_user_id == User.id)
        .where(OperatorAccessRequest.org_id == current_user.org_id)
        .order_by(OperatorAccessRequest.created_at.desc())
    )
    if status_filter != "all":
        query = query.where(OperatorAccessRequest.status == status_filter)

    result = await db.execute(query)
    rows = result.all()

    items: list[OperatorAccessRequestResponse] = []
    for request_item, processed_full_name, processed_username, processed_email in rows:
        processed_name = processed_full_name or processed_username or processed_email or None
        items.append(
            OperatorAccessRequestResponse(
                id=request_item.id,
                org_id=request_item.org_id,
                telegram_id=request_item.telegram_id,
                full_name=request_item.full_name,
                username=request_item.username,
                status=request_item.status,
                processed_by_user_id=request_item.processed_by_user_id,
                processed_by_name=processed_name,
                processed_at=request_item.processed_at,
                rejection_reason=request_item.rejection_reason,
                created_at=request_item.created_at,
            )
        )

    return items


@router.post("/operator-access-requests/{request_id}/approve", response_model=OperatorUserResponse)
async def approve_operator_access_request(
    request_id: uuid.UUID,
    payload: OperatorAccessApproveRequest = Body(default_factory=OperatorAccessApproveRequest),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if payload.role not in {UserRole.MANAGER, UserRole.WORKER}:
        raise HTTPException(status_code=400, detail="Для оператора доступны только роли MANAGER или WORKER.")

    request_result = await db.execute(select(OperatorAccessRequest).where(OperatorAccessRequest.id == request_id))
    access_request = request_result.scalar_one_or_none()
    if not access_request or str(access_request.org_id) != str(current_user.org_id):
        raise HTTPException(status_code=404, detail="Заявка не найдена.")

    user_result = await db.execute(select(User).where(User.telegram_id == access_request.telegram_id))
    operator = user_result.scalar_one_or_none()
    if operator and str(operator.org_id) != str(current_user.org_id):
        raise HTTPException(status_code=400, detail="Пользователь с этим Telegram ID принадлежит другой организации.")

    normalized_username = _normalize_username(payload.username or access_request.username)
    normalized_full_name = (payload.full_name or access_request.full_name or "").strip() or None
    normalized_phone = (payload.phone or "").strip() or None
    normalized_email = (payload.email or "").strip() or None

    if operator is None:
        operator = User(
            org_id=current_user.org_id,
            telegram_id=access_request.telegram_id,
            full_name=normalized_full_name,
            username=normalized_username,
            phone=normalized_phone,
            email=normalized_email,
            role=payload.role,
        )
        db.add(operator)
    else:
        if operator.role == UserRole.ADMIN:
            raise HTTPException(status_code=400, detail="Нельзя изменять роль ADMIN через этот сценарий.")
        operator.role = payload.role
        if normalized_full_name:
            operator.full_name = normalized_full_name
        if normalized_username:
            operator.username = normalized_username
        if normalized_phone:
            operator.phone = normalized_phone
        if normalized_email:
            operator.email = normalized_email

    access_request.status = OperatorAccessRequestStatus.APPROVED.value
    access_request.processed_by_user_id = current_user.id
    access_request.processed_at = datetime.now(timezone.utc)
    access_request.rejection_reason = None

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Не удалось одобрить заявку: {exc}")

    await db.refresh(operator)

    if telegram_bot:
        try:
            login_url = _build_crm_login_url()
            message_text = (
                "✅ Доступ в CRM одобрен.\n"
                f"Войдите по ссылке: {login_url}\n\n"
                "После входа нажмите кнопку открытия бота и подтвердите авторизацию."
            )
            await telegram_bot.send_message(chat_id=access_request.telegram_id, text=message_text)
        except Exception as exc:
            logger.warning("Failed to send approval notification to operator %s: %s", access_request.telegram_id, exc)

    return operator


@router.post("/operator-access-requests/{request_id}/reject", response_model=OperatorAccessRequestResponse)
async def reject_operator_access_request(
    request_id: uuid.UUID,
    payload: OperatorAccessRejectRequest = Body(default_factory=OperatorAccessRejectRequest),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    request_result = await db.execute(select(OperatorAccessRequest).where(OperatorAccessRequest.id == request_id))
    access_request = request_result.scalar_one_or_none()
    if not access_request or str(access_request.org_id) != str(current_user.org_id):
        raise HTTPException(status_code=404, detail="Заявка не найдена.")

    access_request.status = OperatorAccessRequestStatus.REJECTED.value
    access_request.processed_by_user_id = current_user.id
    access_request.processed_at = datetime.now(timezone.utc)
    access_request.rejection_reason = (payload.reason or "").strip() or "Отклонено администратором."

    await db.commit()
    await db.refresh(access_request)

    return OperatorAccessRequestResponse(
        id=access_request.id,
        org_id=access_request.org_id,
        telegram_id=access_request.telegram_id,
        full_name=access_request.full_name,
        username=access_request.username,
        status=access_request.status,
        processed_by_user_id=access_request.processed_by_user_id,
        processed_by_name=current_user.full_name or current_user.username or current_user.email,
        processed_at=access_request.processed_at,
        rejection_reason=access_request.rejection_reason,
        created_at=access_request.created_at,
    )


@router.get("/operators", response_model=list[OperatorUserResponse])
async def list_operators(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .where(
            User.org_id == current_user.org_id,
            User.role.in_([UserRole.MANAGER, UserRole.WORKER]),
        )
        .order_by(User.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/operators", response_model=OperatorUserResponse, status_code=status.HTTP_201_CREATED)
async def create_operator(
    data: OperatorCreateRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if data.role not in {UserRole.MANAGER, UserRole.WORKER}:
        raise HTTPException(status_code=400, detail="Для оператора доступны только роли MANAGER или WORKER.")
    if data.telegram_id <= 0:
        raise HTTPException(status_code=400, detail="Telegram ID должен быть положительным числом.")

    existing = await db.execute(select(User).where(User.telegram_id == data.telegram_id))
    existing_user = existing.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким Telegram ID уже существует.")

    operator = User(
        org_id=current_user.org_id,
        telegram_id=data.telegram_id,
        full_name=(data.full_name or "").strip() or None,
        username=(data.username or "").replace("@", "").strip() or None,
        phone=(data.phone or "").strip() or None,
        email=(data.email or "").strip() or None,
        role=data.role,
    )
    db.add(operator)

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Не удалось создать оператора: {exc}")

    request_result = await db.execute(
        select(OperatorAccessRequest)
        .where(
            OperatorAccessRequest.org_id == current_user.org_id,
            OperatorAccessRequest.telegram_id == data.telegram_id,
            OperatorAccessRequest.status == OperatorAccessRequestStatus.PENDING.value,
        )
        .order_by(OperatorAccessRequest.created_at.desc())
        .limit(1)
    )
    access_request = request_result.scalar_one_or_none()
    if access_request:
        access_request.status = OperatorAccessRequestStatus.APPROVED.value
        access_request.processed_by_user_id = current_user.id
        access_request.processed_at = datetime.now(timezone.utc)
        access_request.rejection_reason = None
        await db.commit()

    await db.refresh(operator)
    return operator


@router.patch("/operators/{user_id}", response_model=OperatorUserResponse)
async def update_operator(
    user_id: uuid.UUID,
    data: OperatorUpdateRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    operator = result.scalar_one_or_none()
    if not operator or str(operator.org_id) != str(current_user.org_id):
        raise HTTPException(status_code=404, detail="Оператор не найден.")

    if operator.role not in {UserRole.MANAGER, UserRole.WORKER}:
        raise HTTPException(status_code=400, detail="Можно редактировать только MANAGER/WORKER.")

    payload = data.model_dump(exclude_unset=True)
    if "role" in payload and payload["role"] is not None and payload["role"] not in {UserRole.MANAGER, UserRole.WORKER}:
        raise HTTPException(status_code=400, detail="Для оператора доступны только роли MANAGER или WORKER.")

    for field_name in ("full_name", "phone", "email", "role"):
        if field_name in payload:
            value = payload[field_name]
            if isinstance(value, str):
                value = value.strip() or None
            setattr(operator, field_name, value)
    if "username" in payload:
        operator.username = (payload["username"] or "").replace("@", "").strip() or None

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Не удалось обновить оператора: {exc}")

    await db.refresh(operator)
    return operator


@router.delete("/operators/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_operator(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if str(user_id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя.")

    result = await db.execute(select(User).where(User.id == user_id))
    operator = result.scalar_one_or_none()
    if not operator or str(operator.org_id) != str(current_user.org_id):
        raise HTTPException(status_code=404, detail="Оператор не найден.")
    if operator.role not in {UserRole.MANAGER, UserRole.WORKER}:
        raise HTTPException(status_code=400, detail="Можно удалить только MANAGER/WORKER.")

    await db.delete(operator)
    await db.commit()
