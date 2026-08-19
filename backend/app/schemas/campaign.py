"""Pydantic schemas for Campaign."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.campaign import CampaignMode, CampaignState, ProviderType


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    mode: CampaignMode = CampaignMode.PROGRESSIVE
    provider: ProviderType = ProviderType.PROVIDER_A
    max_retries: int = Field(default=2, ge=0, le=10)


class CampaignModeUpdate(BaseModel):
    mode: CampaignMode


class CampaignResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    mode: CampaignMode
    state: CampaignState
    provider: ProviderType
    max_retries: int
    created_at: datetime
    updated_at: datetime
