from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class DailyReport(BaseModel):
    """
    Daily report model for workers to submit progress updates.
    Workers use Telegram bot to upload photos/videos and voice notes.
    """
    
    __tablename__ = "daily_reports"
    
    # Project reference
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Author (worker)
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Report content
    content = Column(Text, nullable=False)
    
    # Media URLs (photos, videos, documents)
    # Stored as JSON array: ["https://minio.../photo1.jpg", "https://minio.../video1.mp4"]
    media_urls = Column(JSONB, nullable=True, default=list)
    
    # Relationships
    project = relationship("Project", back_populates="daily_reports")
    author = relationship("User", back_populates="daily_reports")
    
    def __repr__(self):
        return f"<DailyReport(id={self.id}, project_id={self.project_id}, author_id={self.author_id})>"
