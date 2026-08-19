"""Calls router — query and event simulation."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.call import Call, CallState
from app.schemas.call import CallResponse

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.get("", response_model=list[CallResponse])
async def list_calls(
    campaign_id: uuid.UUID | None = Query(default=None),
    state: CallState | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[CallResponse]:
    """List calls with optional filters."""
    query = select(Call).options(selectinload(Call.events))
    if campaign_id:
        query = query.where(Call.campaign_id == campaign_id)
    if state:
        query = query.where(Call.state == state)
    query = query.order_by(Call.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{call_id}", response_model=CallResponse)
async def get_call(call_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> CallResponse:
    """Get a single call with its full event history."""
    result = await db.execute(
        select(Call).where(Call.id == call_id).options(selectinload(Call.events))
    )
    call = result.scalar_one_or_none()
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    return call
