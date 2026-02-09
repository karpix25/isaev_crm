from sqlalchemy import Column, String, ForeignKey, Numeric, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from src.models.base import BaseModel


class ChangeRequestStatus(str, enum.Enum):
    """Change request status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ChangeRequest(BaseModel):
    """
    Change request model for tracking additional work requests.
    When scope changes, manager creates a change request that client must approve.
    """
    
    __tablename__ = "change_requests"
    
    # Project reference
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Change request details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Additional cost
    amount = Column(Numeric(12, 2), nullable=False)
    
    # Status
    status = Column(
        SQLEnum(ChangeRequestStatus, name="change_request_status"),
        nullable=False,
        default=ChangeRequestStatus.PENDING,
        index=True
    )
    
    # Relationships
    project = relationship("Project", back_populates="change_requests")
    
    def __repr__(self):
        return f"<ChangeRequest(id={self.id}, title={self.title}, status={self.status}, amount={self.amount})>"
