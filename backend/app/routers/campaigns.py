"""Campaigns router — lifecycle management."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.campaign import Campaign, CampaignState
from app.schemas.campaign import CampaignCreate, CampaignModeUpdate, CampaignResponse

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)) -> list[CampaignResponse]:
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> CampaignResponse:
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    payload: CampaignCreate, db: AsyncSession = Depends(get_db)
) -> CampaignResponse:
    campaign = Campaign(**payload.model_dump())
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.patch("/{campaign_id}/start", response_model=CampaignResponse)
async def start_campaign(
    campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> CampaignResponse:
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.state not in (CampaignState.DRAFT, CampaignState.PAUSED):
        raise HTTPException(status_code=422, detail=f"Cannot start campaign in state {campaign.state}")
    campaign.state = CampaignState.ACTIVE
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.patch("/{campaign_id}/stop", response_model=CampaignResponse)
async def stop_campaign(
    campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> CampaignResponse:
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.state = CampaignState.COMPLETED
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.patch("/{campaign_id}/mode", response_model=CampaignResponse)
async def update_campaign_mode(
    campaign_id: uuid.UUID,
    payload: CampaignModeUpdate,
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    """Switch between PROGRESSIVE and PREDICTIVE mode live."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.mode = payload.mode
    await db.commit()
    await db.refresh(campaign)
    return campaign
