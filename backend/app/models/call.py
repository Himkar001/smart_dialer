"""Call ORM model and CallState enum."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class CallState(str, PyEnum):
    """All valid call lifecycle states."""
    QUEUED = "QUEUED"
    RESERVED = "RESERVED"
    INITIATED = "INITIATED"
    RINGING = "RINGING"
    ANSWERED = "ANSWERED"
    CONNECTED = "CONNECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Call(Base):
    """
    Represents a single outbound call attempt.

    Idempotency: idempotency_key is unique — duplicate provider events
    that try to insert the same call_event will fail gracefully.

    Out-of-order: the call_state_machine service enforces valid_from_states
    guards before applying any state transition.
    """
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    borrower_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[CallState] = mapped_column(
        Enum(CallState, name="callstate"), nullable=False, default=CallState.QUEUED
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_call_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    initiated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="calls")  # noqa: F821
    agent: Mapped["Agent"] = relationship("Agent", back_populates="calls")  # noqa: F821
    borrower: Mapped["Borrower"] = relationship("Borrower", back_populates="calls")  # noqa: F821
    events: Mapped[list["CallEvent"]] = relationship(  # noqa: F821
        "CallEvent", back_populates="call", order_by="CallEvent.processed_at"
    )

    __table_args__ = (
        Index("ix_calls_state_campaign", "state", "campaign_id"),
        Index("ix_calls_agent", "agent_id"),
    )

    def __repr__(self) -> str:
        return f"<Call id={self.id} state={self.state} agent={self.agent_id}>"
