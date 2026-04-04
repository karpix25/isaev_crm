from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import sqlalchemy as sa
import logging

from src.database import get_db
from src.models import User, Organization
from src.models.user import UserRole
from src.schemas.auth import TokenResponse
from src.services.auth import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

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
    
    # Check if this user exists
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        # Check if database is completely empty (0 users)
        count_result = await db.execute(select(sa.func.count(User.id)))
        total_users = count_result.scalar() or 0
        
        if total_users == 0:
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
                first_name=auth_data.get("first_name"),
                username=auth_data.get("username")
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found. Please contact administrator."
            )
    
    # Create tokens
    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )
