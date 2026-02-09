from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

# --- Daily Report Schemas ---

class DailyReportBase(BaseModel):
    content: str
    media_urls: List[str] = []

class DailyReportCreate(DailyReportBase):
    project_id: UUID

class DailyReportResponse(DailyReportBase):
    id: UUID
    project_id: UUID
    author_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True

# --- Project Stage Schemas ---

class StageBase(BaseModel):
    name: str
    order: int
    is_completed: bool = False

class StageCreate(StageBase):
    project_id: UUID

class StageResponse(StageBase):
    id: UUID
    project_id: UUID
    
    class Config:
        from_attributes = True

# --- Project Schemas ---

class ProjectBase(BaseModel):
    name: str
    address: str
    description: Optional[str] = None
    budget_total: Decimal = Decimal("0.0")
    budget_spent: Decimal = Decimal("0.0")

class ProjectCreate(ProjectBase):
    client_id: Optional[UUID] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    budget_total: Optional[Decimal] = None
    budget_spent: Optional[Decimal] = None
    client_id: Optional[UUID] = None

class ProjectResponse(ProjectBase):
    id: UUID
    org_id: UUID
    client_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class LeadToProjectCreate(BaseModel):
    lead_id: UUID
    project_name: Optional[str] = None
