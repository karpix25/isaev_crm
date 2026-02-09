from sqlalchemy import Column, String, ForeignKey, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from src.models.base import BaseModel


class StageStatus(str, enum.Enum):
    """Stage status"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class Stage(BaseModel):
    """
    Stage model representing a phase of work in a project.
    Examples: "Demolition", "Electrical", "Plumbing", "Finishing"
    """
    
    __tablename__ = "stages"
    
    # Project reference
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Stage details
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    
    # Status
    status = Column(
        SQLEnum(StageStatus, name="stage_status"),
        nullable=False,
        default=StageStatus.NOT_STARTED
    )
    
    # Progress percentage (0-100)
    progress_pct = Column(Integer, nullable=False, default=0)
    
    # Order in the project
    order = Column(Integer, nullable=False, default=0)
    
    # Relationships
    project = relationship("Project", back_populates="stages")
    
    def __repr__(self):
        return f"<Stage(id={self.id}, name={self.name}, status={self.status}, progress={self.progress_pct}%)>"
