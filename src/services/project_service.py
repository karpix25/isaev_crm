import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.project import Project
from src.models.user import User, UserRole
from src.models.lead import Lead
from src.schemas.project import ProjectCreate, ProjectUpdate, LeadToProjectCreate

class ProjectService:
    @staticmethod
    async def create_project(db: AsyncSession, org_id: uuid.UUID, data: ProjectCreate) -> Project:
        project = Project(
            org_id=org_id,
            **data.model_dump()
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project

    @staticmethod
    async def get_projects_by_org(db: AsyncSession, org_id: uuid.UUID) -> List[Project]:
        result = await db.execute(
            select(Project).where(Project.org_id == org_id).order_by(Project.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_project(db: AsyncSession, project_id: uuid.UUID) -> Optional[Project]:
        result = await db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_project(db: AsyncSession, project_id: uuid.UUID, data: ProjectUpdate) -> Optional[Project]:
        project = await ProjectService.get_project(db, project_id)
        if not project:
            return None
        
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(project, key, value)
        
        await db.commit()
        await db.refresh(project)
        return project

    @staticmethod
    async def convert_lead_to_project(db: AsyncSession, org_id: uuid.UUID, data: LeadToProjectCreate) -> Project:
        # 1. Get lead
        result = await db.execute(select(Lead).where(Lead.id == data.lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            raise ValueError("Lead not found")
        
        # Check if already converted
        if lead.converted_to_project_id:
            result = await db.execute(select(Project).where(Project.id == lead.converted_to_project_id))
            project = result.scalar_one_or_none()
            if project:
                return project
        
        # 2. Check if user already exists for this lead (by telegram_id or phone)
        user_result = await db.execute(
            select(User).where(User.telegram_id == lead.telegram_id)
        )
        client = user_result.scalar_one_or_none()
        
        if not client:
            client = User(
                org_id=org_id,
                telegram_id=lead.telegram_id,
                full_name=lead.full_name,
                username=lead.username,
                phone=lead.phone,
                role=UserRole.CLIENT
            )
            db.add(client)
            await db.flush() # Get client.id

        # 3. Create Project
        project = Project(
            org_id=org_id,
            client_id=client.id,
            name=data.project_name or f"Ремонт: {lead.full_name or lead.username}",
            address="Уточняется",
            description=lead.ai_summary,
            budget_total=0
        )
        db.add(project)
        
        # 4. Mark lead as converted
        lead.converted_to_project_id = project.id
        db.add(lead)
        
        await db.commit()
        await db.refresh(project)
        return project
        
    @staticmethod
    async def get_daily_reports(db: AsyncSession, project_id: uuid.UUID) -> List["DailyReport"]:
        from src.models.daily_report import DailyReport
        result = await db.execute(
            select(DailyReport).where(DailyReport.project_id == project_id).order_by(DailyReport.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete_project(db: AsyncSession, project_id: uuid.UUID) -> bool:
        project = await ProjectService.get_project(db, project_id)
        if not project:
            return False
        
        # Clear reference in associated lead
        lead_result = await db.execute(
            select(Lead).where(Lead.converted_to_project_id == project_id)
        )
        lead = lead_result.scalar_one_or_none()
        if lead:
            lead.converted_to_project_id = None
            db.add(lead)
        
        await db.delete(project)
        await db.commit()
        return True

    @staticmethod
    async def update_project_team(db: AsyncSession, project_id: uuid.UUID, foreman_id: Optional[uuid.UUID] = None) -> Optional[Project]:
        project = await ProjectService.get_project(db, project_id)
        if not project:
            return None
        
        # We'll use a many-to-many or specific field. 
        # For Phase 1, the Project model doesn't have a foreman_id field yet.
        # Let's check models/project.py again.
        return project

project_service = ProjectService()
