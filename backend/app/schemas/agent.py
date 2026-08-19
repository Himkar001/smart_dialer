"""Pydantic schemas for Agent."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.agent import AgentState


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    campaign_id: uuid.UUID


class AgentStateUpdate(BaseModel):
    state: AgentState


class AgentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    state: AgentState
    campaign_id: uuid.UUID | None
    reserved_at: datetime | None
    heartbeat_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentBulkCreate(BaseModel):
    campaign_id: uuid.UUID
    count: int = Field(..., ge=1, le=1000)
    name_prefix: str = "Agent"
