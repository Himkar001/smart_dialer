"""Campaign ORM model."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class CampaignMode(str, PyEnum):
    PROGRESSIVE = "PROGRESSIVE"
    PREDICTIVE = "PREDICTIVE"


class CampaignState(str, PyEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class ProviderType(str, PyEnum):
    PROVIDER_A = "PROVIDER_A"
    PROVIDER_B = "PROVIDER_B"


class Campaign(Base):
    """Represents an outbound dialing campaign."""
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mode: Mapped[CampaignMode] = mapped_column(
        Enum(CampaignMode, name="campaignmode"), nullable=False, default=CampaignMode.PROGRESSIVE
    )
    state: Mapped[CampaignState] = mapped_column(
        Enum(CampaignState, name="campaignstate"), nullable=False, default=CampaignState.DRAFT
    )
    provider: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="providertype"), nullable=False, default=ProviderType.PROVIDER_A
    )
    max_retries: Mapped[int] = mapped_column(default=2, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    agents: Mapped[list["Agent"]] = relationship("Agent", back_populates="campaign")  # noqa: F821
    borrowers: Mapped[list["Borrower"]] = relationship("Borrower", back_populates="campaign")  # noqa: F821
    calls: Mapped[list["Call"]] = relationship("Call", back_populates="campaign")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name!r} mode={self.mode} state={self.state}>"
