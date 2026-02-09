from sqlalchemy import Column, String, ForeignKey, Numeric, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from src.models.base import BaseModel


class TransactionType(str, enum.Enum):
    """Transaction type"""
    EXPENSE = "expense"
    INCOME = "income"


class Transaction(BaseModel):
    """
    Transaction model for tracking project finances.
    Records both expenses (materials, labor) and income (client payments).
    """
    
    __tablename__ = "transactions"
    
    # Project reference
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Transaction details
    amount = Column(Numeric(12, 2), nullable=False)
    
    type = Column(
        SQLEnum(TransactionType, name="transaction_type"),
        nullable=False,
        index=True
    )
    
    category = Column(String(100), nullable=True)  # e.g., "materials", "labor", "equipment"
    description = Column(String(500), nullable=True)
    
    # Proof of transaction (receipt photo, invoice)
    proof_url = Column(String(500), nullable=True)
    
    # Relationships
    project = relationship("Project", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, type={self.type}, amount={self.amount})>"
