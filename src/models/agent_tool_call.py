from sqlalchemy import Boolean, Column, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import BaseModel


class AgentToolCall(BaseModel):
    """Audit log for AI-selected CRM tool calls."""

    __tablename__ = "agent_tool_calls"

    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    user_message = Column(Text, nullable=False)
    action = Column(String(80), nullable=False, index=True)
    confidence = Column(Integer, nullable=False, default=0)
    reason = Column(Text, nullable=True)
    args = Column(JSON, nullable=False, default=dict)
    strict_schema = Column(Boolean, nullable=False, default=False)
    executed = Column(Boolean, nullable=False, default=False, index=True)
    result = Column(String(80), nullable=False, default="pending", index=True)
    error = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AgentToolCall(action={self.action}, lead_id={self.lead_id})>"
