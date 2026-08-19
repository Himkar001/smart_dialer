"""Borrower ORM model."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class BorrowerState(str, PyEnum):
    PENDING = "PENDING"
    RESERVED = "RESERVED"
    CALLED = "CALLED"
    COMPLETED = "COMPLETED"
    EXHAUSTED = "EXHAUSTED"


class Borrower(Base):
    """Represents a borrower to be contacted in a campaign."""
    __tablename__ = "borrowers"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[BorrowerState] = mapped_column(
        Enum(BorrowerState, name="borrowerstate"),
        nullable=False,
        default=BorrowerState.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="borrowers")  # noqa: F821
    calls: Mapped[list["Call"]] = relationship("Call", back_populates="borrower")  # noqa: F821

    def __repr__(self) -> str:
        masked = f"***{self.phone[-4:]}" if self.phone and len(self.phone) >= 4 else "***"
        return f"<Borrower id={self.id} phone={masked} state={self.state}>"
