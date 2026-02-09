from sqlalchemy import Column, String, ForeignKey, BigInteger, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from src.models.base import BaseModel


class UserRole(str, enum.Enum):
    """User roles in the system"""
    ADMIN = "admin"
    MANAGER = "manager"
    WORKER = "worker"
    CLIENT = "client"


class User(BaseModel):
    """
    User model supporting multiple roles:
    - Admin: Full access to organization settings
    - Manager: Manages leads and projects
    - Worker: Submits daily reports
    - Client: Views project progress
    """
    
    __tablename__ = "users"
    
    # Organization (multi-tenant)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Telegram integration
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    
    # User details
    phone = Column(String(20), nullable=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    
    # Role
    role = Column(
        SQLEnum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.CLIENT
    )
    
    # Authentication (for admin/manager web login)
    password_hash = Column(String(255), nullable=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="users", foreign_keys=[org_id])
    daily_reports = relationship("DailyReport", back_populates="author", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, role={self.role}, telegram_id={self.telegram_id})>"
