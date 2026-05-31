from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class CompanyFact(BaseModel):
    """Structured company facts used as precise AI context."""

    __tablename__ = "company_facts"
    __table_args__ = (
        UniqueConstraint("org_id", "key", name="uq_company_facts_org_key"),
    )

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, default="company", index=True)
    value_type = Column(String(20), nullable=False, default="text")
    priority = Column(String(20), nullable=False, default="scenario", index=True)
    tags = Column(ARRAY(String), nullable=False, default=list)
    stages = Column(ARRAY(String), nullable=False, default=list)
    questions = Column(ARRAY(String), nullable=False, default=list)
    hint = Column(Text, nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    organization = relationship("Organization")

    def __repr__(self) -> str:
        return f"<CompanyFact(key={self.key}, org_id={self.org_id})>"
