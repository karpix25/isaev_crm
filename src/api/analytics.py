from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.utils import get_default_org_id
from src.database import get_db
from src.dependencies.auth import require_role
from src.models import User, UserRole
from src.schemas.analytics import (
    AnalyticsSummary,
    FunnelEventCreate,
    FunnelEventResponse,
    FunnelSessionCreate,
    FunnelSessionResponse,
)
from src.services.analytics_service import analytics_service
from src.services.analytics_request_enrichment import enrich_funnel_metadata

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post("/funnel/sessions", response_model=FunnelSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_funnel_session(
    request: Request,
    payload: FunnelSessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint for quizzes/landing pages to start a tracked funnel session.
    For now it attaches public traffic to the default organization.
    """
    org_id = await get_default_org_id(db)
    enriched_payload = payload.model_copy(
        update={"metadata": enrich_funnel_metadata(request, payload.metadata)}
    )
    session = await analytics_service.create_session(db=db, org_id=org_id, data=enriched_payload)
    return session


@router.post("/funnel/events", response_model=FunnelEventResponse, status_code=status.HTTP_201_CREATED)
async def record_funnel_event(
    payload: FunnelEventCreate,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint for quizzes/landing pages to append a funnel event."""
    try:
        event = await analytics_service.record_event(
            db=db,
            session_token=payload.session_token,
            event_type=payload.event_type,
            step_id=payload.step_id,
            event_data=payload.event_data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return event


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    source: str | None = Query(None),
    campaign: str | None = Query(None),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_summary(
        db=db,
        org_id=current_user.org_id,
        date_from=date_from,
        date_to=date_to,
        source=source,
        campaign=campaign,
    )
