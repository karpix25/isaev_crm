from pydantic import BaseModel, Field
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime

# Prompt Config Schemas
class PromptConfigBase(BaseModel):
    name: str
    llm_model: Optional[str] = None
    embedding_model: Optional[str] = None
    system_prompt: str
    welcome_message: Optional[str] = None
    handoff_criteria: Optional[str] = None
    is_active: bool = False

class PromptConfigCreate(PromptConfigBase):
    pass

class PromptConfigResponse(PromptConfigBase):
    id: UUID
    org_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Knowledge Base Schemas
class KnowledgeItemBase(BaseModel):
    content: str
    category: Optional[str] = None
    title: Optional[str] = None
    lead_id: Optional[UUID] = None
    metadata_json: Optional[dict] = None

class KnowledgeItemCreate(KnowledgeItemBase):
    pass

class KnowledgeItemResponse(KnowledgeItemBase):
    id: UUID
    org_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class KnowledgeSearchRequest(BaseModel):
    query: str
    limit: int = 5
    category: Optional[str] = None
    lead_id: Optional[UUID] = None


class NovofonSettingsBase(BaseModel):
    dial_url_template: Optional[str] = None
    default_operator_phone: Optional[str] = None
    business_card_template: Optional[str] = None
    business_card_site_url: Optional[str] = None
    business_card_telegram: Optional[str] = None


class NovofonSettingsResponse(NovofonSettingsBase):
    pass


class NovofonSettingsUpdate(NovofonSettingsBase):
    pass
