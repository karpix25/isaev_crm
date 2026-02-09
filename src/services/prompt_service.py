import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from src.models.prompt_config import PromptConfig

class PromptService:
    """Service for managing dynamic AI prompts and model configurations"""
    
    @staticmethod
    async def get_active_config(db: AsyncSession, org_id: uuid.UUID) -> Optional[PromptConfig]:
        """Get the currently active prompt configuration for an organization"""
        result = await db.execute(
            select(PromptConfig)
            .where(and_(PromptConfig.org_id == org_id, PromptConfig.is_active == True))
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_config(
        db: AsyncSession,
        org_id: uuid.UUID,
        name: str,
        system_prompt: str,
        llm_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
        welcome_message: Optional[str] = None,
        handoff_criteria: Optional[str] = None,
        is_active: bool = True
    ) -> PromptConfig:
        """Create a new prompt configuration"""
        if is_active:
            # Deactivate existing active prompt
            await db.execute(
                update(PromptConfig)
                .where(and_(PromptConfig.org_id == org_id, PromptConfig.is_active == True))
                .values(is_active=False)
            )
            
        config = PromptConfig(
            org_id=org_id,
            name=name,
            system_prompt=system_prompt,
            llm_model=llm_model,
            embedding_model=embedding_model,
            welcome_message=welcome_message,
            handoff_criteria=handoff_criteria,
            is_active=is_active
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        return config

    @staticmethod
    async def list_configs(db: AsyncSession, org_id: uuid.UUID) -> List[PromptConfig]:
        """List all prompt configurations for an organization"""
        result = await db.execute(
            select(PromptConfig)
            .where(PromptConfig.org_id == org_id)
            .order_by(PromptConfig.created_at.desc())
        )
        return list(result.scalars().all())

prompt_service = PromptService()
