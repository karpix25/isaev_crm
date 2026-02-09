from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class Organization(BaseModel):
    """
    Organization model for multi-tenant SaaS architecture.
    Each organization represents a separate construction company.
    """
    
    __tablename__ = "organizations"
    
    name = Column(String(255), nullable=False, index=True)
    
    # Owner ID (stored as UUID, but no FK constraint to avoid circular dependency)
    # The owner_id references a User, but we don't enforce it at the database level
    owner_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Relationships
    users = relationship("User", back_populates="organization", foreign_keys="User.org_id")
    leads = relationship("Lead", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")
    custom_fields = relationship("CustomField", back_populates="organization", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Organization(id={self.id}, name={self.name})>"
