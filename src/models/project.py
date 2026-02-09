from sqlalchemy import Column, String, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class Project(BaseModel):
    """
    Project model representing an active renovation project.
    Created when a lead is converted to a paying client.
    """
    
    __tablename__ = "projects"
    
    # Organization (multi-tenant)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Project references
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    foreman_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Project details
    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=False)
    description = Column(String(1000), nullable=True)
    
    # Budget tracking
    budget_total = Column(Numeric(12, 2), nullable=False, default=0)
    budget_spent = Column(Numeric(12, 2), nullable=False, default=0)
    
    # Relationships
    organization = relationship("Organization", back_populates="projects")
    client = relationship("User", foreign_keys=[client_id])
    stages = relationship("Stage", back_populates="project", cascade="all, delete-orphan")
    daily_reports = relationship("DailyReport", back_populates="project", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="project", cascade="all, delete-orphan")
    change_requests = relationship("ChangeRequest", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name}, address={self.address})>"
