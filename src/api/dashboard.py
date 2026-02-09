from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from src.database import get_db
from src.models import User, UserRole
from src.schemas.dashboard import DashboardMetrics
from src.services.dashboard_service import dashboard_service
from src.dependencies.auth import require_role

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """
    Get dashboard metrics and recent AI actions for the organization.
    Requires ADMIN or MANAGER role.
    """
    return await dashboard_service.get_metrics(db, current_user.org_id)
