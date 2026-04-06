from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid
import json

from src.database import get_db
from src.models import User, UserRole, LeadStatus, LeadChangeLog
from src.schemas.lead import (
    LeadCreate,
    LeadResponse,
    LeadListResponse,
    LeadUpdate,
    LeadImportResponse,
    LeadBulkDeleteRequest,
    LeadBulkDeleteResponse,
    LeadChangeLogItem,
    LeadChangeLogResponse,
)
from src.services.lead_service import lead_service
from src.services.lead_import_service import lead_import_service
from src.services.lead_audit_service import lead_audit_service
from src.dependencies.auth import require_role

router = APIRouter(prefix="/leads", tags=["Leads"])


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
