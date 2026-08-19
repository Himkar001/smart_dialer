"""Agent ORM model and AgentState enum."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class AgentState(str, PyEnum):
    """All valid agent lifecycle states."""
    OFFLINE = "OFFLINE"
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    DIALING = "DIALING"
    CONNECTED = "CONNECTED"
    WRAP_UP = "WRAP_UP"
    PAUSED = "PAUSED"


class Agent(Base):
    """
    Represents a collections agent.

    Concurrency note: the AVAILABLE → RESERVED transition is always done via
    SELECT FOR UPDATE SKIP LOCKED to prevent two workers from reserving the
    same agent simultaneously.
    """
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[AgentState] = mapped_column(
        Enum(AgentState, name="agentstate"), nullable=False, default=AgentState.OFFLINE
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="agents")  # noqa: F821
    calls: Mapped[list["Call"]] = relationship("Call", back_populates="agent")  # noqa: F821

    __table_args__ = (
        # Fast lookup: find AVAILABLE agents for a campaign
        Index("ix_agents_state_campaign", "state", "campaign_id"),
        # Fast lookup: find stale reservations by heartbeat
        Index("ix_agents_heartbeat", "heartbeat_at"),
    )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name={self.name!r} state={self.state}>"
