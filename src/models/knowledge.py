from sqlalchemy import Column, String, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from src.models.base import BaseModel

class KnowledgeItem(BaseModel):
    """
    Knowledge Base item for RAG.
    Stores chunks of text with their embeddings.
    """
    __tablename__ = "knowledge_base"

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    category = Column(String(100), nullable=True) # e.g., "pricing", "FAQ", "portfolio"
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    
    # Vector embedding (1536 is standard for OpenAI/OpenRouter embeddings)
    embedding = Column(Vector(1536), nullable=True)
    
    metadata_json = Column(JSON, nullable=True) # Extra info like source URL, tags

    def __repr__(self):
        return f"<KnowledgeItem(id={self.id}, title={self.title}, category={self.category})>"
