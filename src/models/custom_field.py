from sqlalchemy import Column, String, ForeignKey, Boolean, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
import enum

from src.models.base import BaseModel


class FieldType(str, enum.Enum):
    """Custom field types"""
    TEXT = "text"
    NUMBER = "number"
    SELECT = "select"
    BOOLEAN = "boolean"


class CustomField(BaseModel):
    """
    Custom fields that organizations can define for lead qualification.
    These fields are automatically injected into the AI prompt and saved to extracted_data.
    """
    
    __tablename__ = "custom_fields"
    
    # Organization (multi-tenant)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Field definition
    field_name = Column(String(100), nullable=False)  # e.g., "foundation_type" (snake_case)
    field_label = Column(String(255), nullable=False)  # e.g., "Тип фундамента" (display name)
    field_type = Column(String(20), nullable=False, default="text")  # text, number, select, boolean
    
    # Options for SELECT type (JSON array of strings)
    options = Column(JSON, nullable=True)  # e.g., ["лента", "плита", "сваи"]
    
    # Description/hint for the field
    description = Column(Text, nullable=True)
    
    # Active status
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Display order
    display_order = Column(String(10), nullable=False, default="0")
    
    # Relationships
    organization = relationship("Organization", back_populates="custom_fields")
    
    def __repr__(self):
        return f"<CustomField(field_name={self.field_name}, org_id={self.org_id})>"
