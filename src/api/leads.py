from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid
import json

from src.database import get_db
from src.config import settings
from src.models import User, UserRole, LeadStatus, LeadChangeLog, LeadCallEvent
from src.schemas.lead import (
    LeadCreate,
    LeadResponse,
    LeadListResponse,
    LeadUpdate,
    LeadImportResponse,
    LeadBulkDeleteRequest,
    LeadBulkDeleteResponse,
    LeadCallStartRequest,
    LeadCallStartResponse,
    LeadDialPrepareRequest,
    LeadDialPrepareResponse,
    LeadChangeLogItem,
    LeadChangeLogResponse,
)
from src.services.lead_service import lead_service
from src.services.lead_import_service import lead_import_service
from src.services.lead_audit_service import lead_audit_service
from src.services.novofon_service import novofon_service, NovofonApiError
from src.dependencies.auth import require_role

router = APIRouter(prefix="/leads", tags=["Leads"])


async def _build_business_card_message(
    db: AsyncSession,
    current_user: User,
    operator_phone: str,
    custom_message: Optional[str] = None,
) -> str:
    if custom_message and custom_message.strip():
        return custom_message.strip()

    org_settings = await novofon_service.get_org_settings(db, current_user.org_id)

    return novofon_service.render_business_card_message(
        company_name=org_settings.get("organization_name"),
        manager_name=current_user.full_name,
        manager_phone=operator_phone or current_user.phone,
        template=org_settings.get("business_card_template"),
        default_operator_phone=org_settings.get("default_operator_phone"),
        site_url=org_settings.get("business_card_site_url"),
        telegram_username=org_settings.get("business_card_telegram"),
    )


@router.get("/", response_model=LeadListResponse)
async def get_leads(
    status: Optional[LeadStatus] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """
    Get paginated list of leads for the organization.
    Supports filtering by status, source, and search query.
    Requires ADMIN or MANAGER role.
    """
    leads, total = await lead_service.get_leads_by_org(
        db=db,
        org_id=current_user.org_id,
        status=status,
        source=source,
        search=search,
        page=page,
        page_size=page_size
    )
    
    return LeadListResponse(
        leads=[LeadResponse.model_validate(lead) for lead in leads],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_data: LeadCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually create a new lead from the CRM interface.
    Requires ADMIN or MANAGER role.
    """
    # Override org_id to match the current user's org
    from sqlalchemy.exc import IntegrityError
    
    try:
        lead = await lead_service.create_manual_lead(
            db=db,
            org_id=current_user.org_id,
            full_name=lead_data.full_name,
            phone=lead_data.phone,
            username=lead_data.username,
            source=lead_data.source or "CRM"
        )
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот пользователь (с таким Telegram ID, номером телефона или никнеймом) уже существует в CRM."
        )

    create_changes = {
        "full_name": {"old": None, "new": lead.full_name},
        "phone": {"old": None, "new": lead.phone},
        "username": {"old": None, "new": lead.username},
        "status": {"old": None, "new": lead.status},
        "telegram_lookup_status": {"old": None, "new": lead.telegram_lookup_status},
    }
    await lead_audit_service.log_change(
        db=db,
        lead=lead,
        action="created",
        source="manual",
        user_id=current_user.id,
        changes=create_changes,
    )
    await db.commit()
    
    return LeadResponse.model_validate(lead)


@router.post("/import", response_model=LeadImportResponse)
async def import_leads(
    file: UploadFile = File(...),
    source: str = Form("IMPORT"),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk import leads from .xlsx or .csv with automatic column detection.
    Requires ADMIN or MANAGER role.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл не выбран."
        )

    content = await file.read()

    try:
        result = await lead_import_service.import_leads_from_file(
            db=db,
            org_id=current_user.org_id,
            filename=file.filename,
            file_bytes=content,
            source=source or "IMPORT",
            actor_user_id=current_user.id,
        )
        return LeadImportResponse(**result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )


@router.post("/bulk-delete", response_model=LeadBulkDeleteResponse)
async def bulk_delete_leads(
    payload: LeadBulkDeleteRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk delete leads and their chat messages by IDs.
    Requires ADMIN role.
    """
    if not payload.lead_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Список lead_ids пуст."
        )

    deleted = await lead_service.bulk_delete_leads(
        db=db,
        org_id=current_user.org_id,
        lead_ids=payload.lead_ids
    )
    return LeadBulkDeleteResponse(requested=len(payload.lead_ids), deleted=deleted)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """
    Get lead details by ID.
    Requires ADMIN or MANAGER role.
    """
    lead = await lead_service.get_lead_by_id(db, lead_id)
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    if str(lead.org_id) != str(current_user.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return LeadResponse.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    lead_data: LeadUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """
    Update lead details.
    Requires ADMIN or MANAGER role.
    """
    lead = await lead_service.get_lead_by_id(db, lead_id)
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    if str(lead.org_id) != str(current_user.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    payload = lead_data.model_dump(exclude_unset=True)
    tracked_fields = (
        "full_name",
        "phone",
        "status",
        "ai_summary",
        "operator_comment",
        "avatar_url",
        "readiness_score",
        "extracted_data",
        "telegram_lookup_status",
        "telegram_lookup_error",
    )
    before_state = {field_name: getattr(lead, field_name, None) for field_name in tracked_fields}
    for field_name in (
        "full_name",
        "phone",
        "status",
        "ai_summary",
        "operator_comment",
        "avatar_url",
        "readiness_score",
        "extracted_data",
        "telegram_lookup_status",
        "telegram_lookup_error",
    ):
        if field_name in payload:
            setattr(lead, field_name, payload[field_name])

    after_state = {field_name: getattr(lead, field_name, None) for field_name in tracked_fields}
    changes = lead_audit_service.build_field_changes(before_state, after_state)
    if changes:
        await lead_audit_service.log_change(
            db=db,
            lead=lead,
            action="updated",
            source="manual",
            user_id=current_user.id,
            changes=changes,
        )
    
    await db.commit()
    await db.refresh(lead)
    
    return LeadResponse.model_validate(lead)


@router.post("/{lead_id}/call", response_model=LeadCallStartResponse)
async def start_lead_call(
    lead_id: uuid.UUID,
    payload: LeadCallStartRequest = Body(default_factory=LeadCallStartRequest),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    """
    Start click-to-call via Novofon for a lead phone number.
    """
    lead = await lead_service.get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    if str(lead.org_id) != str(current_user.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    if not lead.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У лида не указан номер телефона.",
        )
    if not novofon_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Novofon не настроен. Проверьте переменные окружения.",
        )
    org_settings = await novofon_service.get_org_settings(db, current_user.org_id)

    operator_phone = (
        (payload.operator_phone or "").strip()
        or (current_user.phone or "").strip()
        or (org_settings.get("default_operator_phone") or "").strip()
        or (settings.novofon_default_operator_phone or "").strip()
    )
    if not operator_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось определить номер сотрудника для звонка. Укажите номер в профиле пользователя или NOVOFON_DEFAULT_OPERATOR_PHONE.",
        )

    business_card_message = await _build_business_card_message(
        db=db,
        current_user=current_user,
        operator_phone=operator_phone,
        custom_message=payload.business_card_message,
    )

    event_id = uuid.uuid4()
    call_event = LeadCallEvent(
        id=event_id,
        org_id=current_user.org_id,
        lead_id=lead.id,
        initiated_by_user_id=current_user.id,
        operator_phone=operator_phone,
        contact_phone=lead.phone,
        external_id=str(event_id),
        call_status="starting",
        business_card_message=business_card_message,
        business_card_status="pending",
    )
    db.add(call_event)

    try:
        call_result = await novofon_service.start_employee_call(
            operator_phone=operator_phone,
            contact_phone=lead.phone,
            external_id=str(event_id),
            virtual_phone_number=settings.novofon_virtual_phone_number,
        )
        call_event.call_status = "initiated"
        call_event.call_session_id = call_result.get("call_session_id")
        call_event.operator_phone = call_result.get("operator_phone") or operator_phone
        call_event.contact_phone = call_result.get("contact_phone") or lead.phone
        call_event.novofon_response_json = json.dumps(call_result.get("response") or {}, ensure_ascii=False)

        await lead_audit_service.log_change(
            db=db,
            lead=lead,
            action="call_started",
            source="novofon",
            user_id=current_user.id,
            changes={
                "call_session_id": {"old": None, "new": call_event.call_session_id},
                "call_to": {"old": None, "new": call_event.contact_phone},
            },
        )

        await db.commit()
        return LeadCallStartResponse(
            event_id=call_event.id,
            call_status=call_event.call_status,
            call_session_id=call_event.call_session_id,
            detail="Звонок запущен. После успешного завершения визитка отправится автоматически.",
        )
    except NovofonApiError as exc:
        call_event.call_status = "failed"
        call_event.business_card_status = "failed"
        call_event.business_card_error = exc.message
        call_event.novofon_response_json = json.dumps(
            {"error": {"message": exc.message, "mnemonic": exc.mnemonic, "code": exc.code}},
            ensure_ascii=False,
        )
        await lead_audit_service.log_change(
            db=db,
            lead=lead,
            action="call_failed",
            source="novofon",
            user_id=current_user.id,
            changes={"call_error": {"old": None, "new": exc.message}},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Novofon error: {exc.message}",
        )
    except Exception as exc:
        call_event.call_status = "failed"
        call_event.business_card_status = "failed"
        call_event.business_card_error = str(exc)
        call_event.novofon_response_json = json.dumps({"error": str(exc)}, ensure_ascii=False)
        await lead_audit_service.log_change(
            db=db,
            lead=lead,
            action="call_failed",
            source="novofon",
            user_id=current_user.id,
            changes={"call_error": {"old": None, "new": str(exc)}},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось запустить звонок.",
        )


@router.post("/{lead_id}/dial/prepare", response_model=LeadDialPrepareResponse)
async def prepare_lead_dial(
    lead_id: uuid.UUID,
    payload: LeadDialPrepareRequest = Body(default_factory=LeadDialPrepareRequest),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    """
    Register manual dial intent and return dial URL for desktop softphone.
    """
    lead = await lead_service.get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    if str(lead.org_id) != str(current_user.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    if not lead.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У лида не указан номер телефона.",
        )
    org_settings = await novofon_service.get_org_settings(db, current_user.org_id)

    operator_phone = (
        (payload.operator_phone or "").strip()
        or (current_user.phone or "").strip()
        or (org_settings.get("default_operator_phone") or "").strip()
        or (settings.novofon_default_operator_phone or "").strip()
    )
    if not operator_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось определить номер сотрудника для звонка. Укажите номер в профиле пользователя или NOVOFON_DEFAULT_OPERATOR_PHONE.",
        )

    business_card_message = await _build_business_card_message(
        db=db,
        current_user=current_user,
        operator_phone=operator_phone,
        custom_message=payload.business_card_message,
    )

    event_id = uuid.uuid4()
    call_event = LeadCallEvent(
        id=event_id,
        org_id=current_user.org_id,
        lead_id=lead.id,
        initiated_by_user_id=current_user.id,
        operator_phone=operator_phone,
        contact_phone=lead.phone,
        external_id=str(event_id),
        call_status="manual_dial_requested",
        business_card_message=business_card_message,
        business_card_status="pending",
    )
    db.add(call_event)
    await lead_audit_service.log_change(
        db=db,
        lead=lead,
        action="manual_dial_opened",
        source="novofon",
        user_id=current_user.id,
        changes={"dial_to": {"old": None, "new": lead.phone}},
    )
    await db.commit()

    return LeadDialPrepareResponse(
        event_id=event_id,
        dial_url=novofon_service.build_dial_url(
            lead.phone,
            template=(org_settings.get("dial_url_template") or settings.novofon_dial_url_template),
        ),
        detail="Открываем софтфон и номер для набора.",
    )


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete lead and all associated chat messages.
    Requires ADMIN role.
    """
    lead = await lead_service.get_lead_by_id(db, lead_id)
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    if str(lead.org_id) != str(current_user.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    await lead_service.delete_lead(db, lead_id)


@router.get("/{lead_id}/history", response_model=LeadChangeLogResponse)
async def get_lead_history(
    lead_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    lead = await lead_service.get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )

    if str(lead.org_id) != str(current_user.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    result = await db.execute(
        select(LeadChangeLog, User.full_name, User.email)
        .outerjoin(User, LeadChangeLog.user_id == User.id)
        .where(
            LeadChangeLog.lead_id == lead_id,
            LeadChangeLog.org_id == current_user.org_id,
        )
        .order_by(LeadChangeLog.created_at.desc())
        .limit(limit)
    )
    rows = result.all()

    items: list[LeadChangeLogItem] = []
    for log_item, user_full_name, user_email in rows:
        parsed_changes = {}
        if log_item.changes_json:
            try:
                parsed_changes = json.loads(log_item.changes_json)
            except Exception:
                parsed_changes = {}
        user_name = user_full_name or user_email or None
        items.append(
            LeadChangeLogItem(
                id=log_item.id,
                action=log_item.action,
                source=log_item.source,
                user_id=log_item.user_id,
                user_name=user_name,
                changes=parsed_changes,
                created_at=log_item.created_at,
            )
        )

    return LeadChangeLogResponse(items=items)
