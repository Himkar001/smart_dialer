"""Pydantic schemas for Call and CallEvent."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.call import CallState


class CallEventResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    event_type: str
    idempotency_key: str
    raw_payload: dict | None
    processed_at: datetime


class CallResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    campaign_id: uuid.UUID
    agent_id: uuid.UUID | None
    borrower_id: uuid.UUID
    state: CallState
    provider: str
    provider_call_id: str | None
    attempt: int
    initiated_at: datetime | None
    connected_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    events: list[CallEventResponse] = []
