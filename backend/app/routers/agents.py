"""Agents router — CRUD and state management."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent, AgentState
from app.models.campaign import Campaign
from app.schemas.agent import AgentBulkCreate, AgentResponse, AgentStateUpdate
from app.services.agent_state_machine import InvalidTransitionError, transition_agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    campaign_id: uuid.UUID | None = Query(default=None),
    state: AgentState | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[AgentResponse]:
    """List agents, optionally filtered by campaign and/or state."""
    query = select(Agent)
    if campaign_id:
        query = query.where(Agent.campaign_id == campaign_id)
    if state:
        query = query.where(Agent.state == state)
    result = await db.execute(query.order_by(Agent.created_at))
    return list(result.scalars().all())


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> AgentResponse:
    """Get a single agent by ID."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/bulk", response_model=list[AgentResponse], status_code=201)
async def create_agents_bulk(
    payload: AgentBulkCreate, db: AsyncSession = Depends(get_db)
) -> list[AgentResponse]:
    """Create multiple agents for a campaign in bulk."""
    # Verify campaign exists
    result = await db.execute(select(Campaign).where(Campaign.id == payload.campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    agents = [
        Agent(
            name=f"{payload.name_prefix} {i + 1}",
            state=AgentState.AVAILABLE,
            campaign_id=payload.campaign_id,
        )
        for i in range(payload.count)
    ]
    db.add_all(agents)
    await db.commit()
    for a in agents:
        await db.refresh(a)
    return agents


@router.patch("/{agent_id}/state", response_model=AgentResponse)
async def update_agent_state(
    agent_id: uuid.UUID,
    payload: AgentStateUpdate,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Manually update agent state (for testing / admin purposes)."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        async with db.begin_nested():
            await transition_agent(db, agent, payload.state)
        await db.commit()
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    await db.refresh(agent)
    return agent
