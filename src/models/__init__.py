"""
SQLAlchemy models for Renovation CRM.
All models use multi-tenant architecture with org_id for data isolation.
"""

from src.models.base import BaseModel
from src.models.organization import Organization
from src.models.user import User, UserRole
from src.models.lead import Lead, LeadStatus
from src.models.chat_message import ChatMessage, MessageDirection
from src.models.project import Project
from src.models.stage import Stage, StageStatus
from src.models.daily_report import DailyReport
from src.models.transaction import Transaction, TransactionType
from src.models.change_request import ChangeRequest, ChangeRequestStatus
from src.models.knowledge import KnowledgeItem
from src.models.prompt_config import PromptConfig
from src.models.custom_field import CustomField, FieldType

__all__ = [
    "BaseModel",
    "Organization",
    "User",
    "UserRole",
    "Lead",
    "LeadStatus",
    "ChatMessage",
    "MessageDirection",
    "Project",
    "Stage",
    "StageStatus",
    "DailyReport",
    "Transaction",
    "TransactionType",
    "ChangeRequest",
    "ChangeRequestStatus",
    "KnowledgeItem",
    "PromptConfig",
    "CustomField",
    "FieldType",
]
