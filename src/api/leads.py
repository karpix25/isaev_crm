from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid

from src.database import get_db
from src.models import User, UserRole, LeadStatus
from src.schemas.lead import LeadCreate, LeadResponse, LeadListResponse, LeadUpdate
from src.services.lead_service import lead_service
from src.dependencies.auth import get_current_user, require_role

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
    lead = await lead_service.create_manual_lead(
        db=db,
        org_id=current_user.org_id,
        full_name=lead_data.full_name,
        phone=lead_data.phone,
        source=lead_data.source or "CRM"
    )
    
    return LeadResponse.model_validate(lead)


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
    
    # Update fields
    if lead_data.full_name is not None:
        lead.full_name = lead_data.full_name
    if lead_data.phone is not None:
        lead.phone = lead_data.phone
    if lead_data.status is not None:
        lead.status = lead_data.status
    if lead_data.ai_summary is not None:
        lead.ai_summary = lead_data.ai_summary
    
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
