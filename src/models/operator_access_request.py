import enum

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import BaseModel


class OperatorAccessRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OperatorAccessRequest(BaseModel):
    __tablename__ = "operator_access_requests"

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_id = Column(BigInteger, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default=OperatorAccessRequestStatus.PENDING.value, index=True)
    processed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String(500), nullable=True)
