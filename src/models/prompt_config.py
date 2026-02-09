from sqlalchemy import Column, String, Text, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from src.models.base import BaseModel

class PromptConfig(BaseModel):
    """
    Dynamic configuration for AI Prompts.
    Allows changing system prompts, welcome messages, and handoff criteria without code changes.
    """
    __tablename__ = "prompt_configs"

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    name = Column(String(100), nullable=False) # e.g., "sales_agent_v1"
    llm_model = Column(String(100), nullable=True) # e.g., "openai/gpt-4-turbo"
    embedding_model = Column(String(100), nullable=True) # e.g., "text-embedding-3-small"
    
    system_prompt = Column(Text, nullable=False)
    welcome_message = Column(Text, nullable=True)
    handoff_criteria = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=False) # Only one active prompt per org/task

    def __repr__(self):
        return f"<PromptConfig(id={self.id}, name={self.name}, is_active={self.is_active})>"
