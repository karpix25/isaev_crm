from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from src.database import Base


class BaseModel(Base):
    """Base model with common fields for all tables"""
    
    __abstract__ = True
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        index=True
    )
    
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
