"""CallEvent audit log ORM model."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class CallEvent(Base):
    """
    Immutable audit log of every provider event for a call.

    idempotency_key is UNIQUE — if a provider sends the same event twice,
    the second INSERT fails with a unique constraint error, which we catch
    and silently ignore. The call state is not changed.
    """
    __tablename__ = "call_events"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), primary_key=True, default=uuid.uuid4
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    # Use sa.JSON for cross-DB compatibility (JSONB in PostgreSQL, JSON in SQLite)
    raw_payload: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    call: Mapped["Call"] = relationship("Call", back_populates="events")  # noqa: F821

    def __repr__(self) -> str:
        return f"<CallEvent call={self.call_id} type={self.event_type}>"
