from sqlalchemy import Column, String, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class LeadCallEvent(BaseModel):
    __tablename__ = "lead_call_events"

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    initiated_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    operator_phone = Column(String(32), nullable=False, index=True)
    contact_phone = Column(String(32), nullable=False, index=True)
    external_id = Column(String(128), nullable=False, unique=True, index=True)
    call_session_id = Column(String(64), nullable=True, index=True)

    call_status = Column(String(32), nullable=False, default="initiated", index=True)
    disposition = Column(String(64), nullable=True)
    record_link = Column(Text, nullable=True)
    call_started_at = Column(DateTime(timezone=True), nullable=True)
    call_ended_at = Column(DateTime(timezone=True), nullable=True)

    business_card_message = Column(Text, nullable=True)
    business_card_status = Column(String(32), nullable=False, default="pending", index=True)
    business_card_sent_at = Column(DateTime(timezone=True), nullable=True)
    business_card_error = Column(Text, nullable=True)

    novofon_response_json = Column(Text, nullable=True)
    webhook_payload_json = Column(Text, nullable=True)

    lead = relationship("Lead", back_populates="call_events")
    initiated_by = relationship("User")
