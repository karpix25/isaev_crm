from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from src.database import get_db
from src.models import User, UserRole
from src.schemas.ai import (
    PromptConfigCreate, PromptConfigResponse,
    KnowledgeItemCreate, KnowledgeItemResponse,
    KnowledgeSearchRequest
)
from src.services.prompt_service import prompt_service
from src.services.knowledge_service import knowledge_service
from src.dependencies.auth import get_current_user, require_role

router = APIRouter(prefix="/ai", tags=["AI Configuration"])

# --- Prompt Management ---

@router.get("/prompts", response_model=List[PromptConfigResponse])
async def list_prompts(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """List all AI prompt configurations"""
    return await prompt_service.list_configs(db, current_user.org_id)

@router.post("/prompts", response_model=PromptConfigResponse)
async def create_prompt(
    data: PromptConfigCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Create a new AI prompt configuration and optionally make it active"""
    return await prompt_service.create_config(
        db=db,
        org_id=current_user.org_id,
        **data.model_dump()
    )

@router.get("/prompts/active", response_model=PromptConfigResponse)
async def get_active_prompt(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """Get the currently active AI configuration"""
    config = await prompt_service.get_active_config(db, current_user.org_id)
    if not config:
        raise HTTPException(status_code=404, detail="No active AI configuration found")
    return config

# --- Knowledge Base Management ---

@router.post("/knowledge", response_model=KnowledgeItemResponse)
async def add_knowledge(
    data: KnowledgeItemCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Add a new item to the Knowledge Base (generates embeddings)"""
    return await knowledge_service.add_knowledge_item(
        db=db,
        org_id=current_user.org_id,
        **data.model_dump()
    )

@router.get("/knowledge", response_model=List[KnowledgeItemResponse])
async def list_knowledge(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """List all Knowledge Base items for an organization"""
    from sqlalchemy import select
    from src.models.knowledge import KnowledgeItem
    
    result = await db.execute(
        select(KnowledgeItem)
        .where(KnowledgeItem.org_id == current_user.org_id)
        .order_by(KnowledgeItem.created_at.desc())
    )
    return list(result.scalars().all())

@router.delete("/knowledge/{item_id}")
async def delete_knowledge_item(
    item_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Delete an item from the Knowledge Base"""
    from src.models.knowledge import KnowledgeItem
    from sqlalchemy import delete
    
    await db.execute(
        delete(KnowledgeItem)
        .where(KnowledgeItem.id == item_id)
        .where(KnowledgeItem.org_id == current_user.org_id)
    )
    await db.commit()
    return {"status": "success"}

@router.post("/knowledge/search", response_model=List[KnowledgeItemResponse])
async def search_knowledge(
    data: KnowledgeSearchRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """Test semantic search in the Knowledge Base"""
    # Get active config to know which embedding model was used for indexing
    config = await prompt_service.get_active_config(db, current_user.org_id)
    embedding_model = config.embedding_model if config else None
    
    return await knowledge_service.search_knowledge(
        db=db,
        org_id=current_user.org_id,
        query=data.query,
        limit=data.limit,
        category=data.category,
        embedding_model=embedding_model
    )

@router.post("/knowledge/upload")
async def upload_knowledge_file(
    category: str = Form("general"),
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Upload and process a knowledge base file (PDF/TXT)"""
    try:
        content = await file.read()
        
        # Get active config to know which embedding model to use
        config = await prompt_service.get_active_config(db, current_user.org_id)
        embedding_model = config.embedding_model if config else None
        
        count = await knowledge_service.process_knowledge_file(
            db=db,
            org_id=current_user.org_id,
            file_content=content,
            filename=file.filename,
            category=category,
            embedding_model=embedding_model
        )
        
        return {"status": "success", "indexed_chunks": count}
    except ValueError as e:
        import logging
        logging.getLogger(__name__).warning(f"Knowledge upload validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Knowledge upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка индексации файла: {str(e)}"
        )
