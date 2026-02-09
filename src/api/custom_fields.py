"""
API endpoints for managing custom fields.
Custom fields allow organizations to define additional data fields for lead qualification.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
from uuid import UUID
from datetime import datetime
import re

from src.database import get_db
from src.models import CustomField, FieldType
from src.dependencies.auth import get_current_user
from src.models.user import User
from pydantic import BaseModel, Field, validator


# Pydantic schemas
class CustomFieldCreate(BaseModel):
    field_name: str = Field(..., min_length=1, max_length=100)
    field_label: str = Field(..., min_length=1, max_length=255)
    field_type: str = Field(..., pattern="^(text|number|select|boolean)$")
    options: List[str] | None = None
    description: str | None = None
    display_order: str = "0"
    
    @validator('field_name')
    def validate_field_name(cls, v):
        """Ensure field_name is snake_case"""
        if not re.match(r'^[a-z][a-z0-9_]*$', v):
            raise ValueError('field_name must be snake_case (lowercase letters, numbers, underscores)')
        return v
    
    @validator('options')
    def validate_options(cls, v, values):
        """Ensure options are provided for select type"""
        if values.get('field_type') == 'select' and not v:
            raise ValueError('options are required for select field type')
        return v


class CustomFieldUpdate(BaseModel):
    field_label: str | None = Field(None, min_length=1, max_length=255)
    field_type: str | None = Field(None, pattern="^(text|number|select|boolean)$")
    options: List[str] | None = None
    description: str | None = None
    is_active: bool | None = None
    display_order: str | None = None


class CustomFieldResponse(BaseModel):
    id: UUID
    org_id: UUID
    field_name: str
    field_label: str
    field_type: str
    options: List[str] | None
    description: str | None
    is_active: bool
    display_order: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


router = APIRouter(prefix="/custom-fields", tags=["custom-fields"])


@router.get("", response_model=List[CustomFieldResponse])
async def list_custom_fields(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    active_only: bool = True
):
    """
    List all custom fields for the current organization.
    
    Args:
        active_only: If True, only return active fields (default: True)
    """
    query = select(CustomField).where(CustomField.org_id == current_user.org_id)
    
    if active_only:
        query = query.where(CustomField.is_active == True)
    
    query = query.order_by(CustomField.display_order, CustomField.created_at)
    
    result = await db.execute(query)
    fields = result.scalars().all()
    
    return fields


@router.post("", response_model=CustomFieldResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_field(
    field_data: CustomFieldCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new custom field for the organization.
    """
    # Check if field_name already exists for this org
    existing = await db.execute(
        select(CustomField).where(
            and_(
                CustomField.org_id == current_user.org_id,
                CustomField.field_name == field_data.field_name
            )
        )
    )
    
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Field with name '{field_data.field_name}' already exists"
        )
    
    # Create new custom field
    new_field = CustomField(
        org_id=current_user.org_id,
        field_name=field_data.field_name,
        field_label=field_data.field_label,
        field_type=field_data.field_type,
        options=field_data.options,
        description=field_data.description,
        display_order=field_data.display_order,
        is_active=True
    )
    
    db.add(new_field)
    await db.commit()
    await db.refresh(new_field)
    
    return new_field


@router.get("/{field_id}", response_model=CustomFieldResponse)
async def get_custom_field(
    field_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific custom field by ID.
    """
    result = await db.execute(
        select(CustomField).where(
            and_(
                CustomField.id == field_id,
                CustomField.org_id == current_user.org_id
            )
        )
    )
    
    field = result.scalar_one_or_none()
    
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom field not found"
        )
    
    return field


@router.put("/{field_id}", response_model=CustomFieldResponse)
async def update_custom_field(
    field_id: UUID,
    field_data: CustomFieldUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing custom field.
    Note: field_name cannot be changed to maintain data integrity.
    """
    result = await db.execute(
        select(CustomField).where(
            and_(
                CustomField.id == field_id,
                CustomField.org_id == current_user.org_id
            )
        )
    )
    
    field = result.scalar_one_or_none()
    
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom field not found"
        )
    
    # Update fields
    update_data = field_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(field, key, value)
    
    await db.commit()
    await db.refresh(field)
    
    return field


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_field(
    field_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a custom field.
    Note: This will remove the field definition, but existing data in extracted_data will remain.
    """
    result = await db.execute(
        select(CustomField).where(
            and_(
                CustomField.id == field_id,
                CustomField.org_id == current_user.org_id
            )
        )
    )
    
    field = result.scalar_one_or_none()
    
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom field not found"
        )
    
    await db.delete(field)
    await db.commit()
    
    return None
