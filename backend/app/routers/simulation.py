"""Simulation control router."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.providers.registry import get_all_providers
from app.services.simulation_runner import (
    get_simulation_state,
    start_simulation,
    stop_simulation,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/simulation", tags=["simulation"])


class StartSimulationRequest(BaseModel):
    agent_count: int = Field(default=20, ge=1, le=500)
    borrower_count: int = Field(default=100, ge=1, le=5000)
    mode: str = Field(default="PROGRESSIVE", pattern="^(PROGRESSIVE|PREDICTIVE)$")
    provider: str = Field(default="PROVIDER_A", pattern="^(PROVIDER_A|PROVIDER_B)$")
    answer_rate_override: float | None = Field(default=None, ge=0.0, le=1.0)


@router.post("/start")
async def start(payload: StartSimulationRequest) -> dict:
    """Start a new simulation. Stops any existing simulation first."""
    campaign_id = await start_simulation(
        agent_count=payload.agent_count,
        borrower_count=payload.borrower_count,
        mode=payload.mode,
        provider_type=payload.provider,
        answer_rate_override=payload.answer_rate_override,
    )
    return {
        "message": "Simulation started",
        "campaign_id": str(campaign_id),
        "agent_count": payload.agent_count,
        "borrower_count": payload.borrower_count,
        "mode": payload.mode,
        "provider": payload.provider,
    }


@router.post("/stop")
async def stop() -> dict:
    """Stop the running simulation."""
    await stop_simulation()
    return {"message": "Simulation stopped"}


@router.get("/status")
async def status() -> dict:
    """Return current simulation status."""
    state = get_simulation_state()
    return {
        "is_running": state.is_running,
        "campaign_id": str(state.campaign_id) if state.campaign_id else None,
        "started_at": state.started_at.isoformat() if state.started_at else None,
        "mode": state.mode,
        "provider": state.provider_type,
    }


@router.post("/trigger/{scenario}")
async def trigger_scenario(scenario: str) -> dict:
    """
    Trigger a failure scenario for demonstration.
    Available: provider-outage, provider-restore, agent-drop (Sprint 4 full implementation).
    """
    state = get_simulation_state()
    if not state.is_running:
        raise HTTPException(status_code=400, detail="No simulation running")

    providers = get_all_providers()

    if scenario == "provider-outage":
        from app.providers.provider_b import ProviderB
        pb = providers.get("PROVIDER_B")
        if isinstance(pb, ProviderB):
            pb.simulate_outage()
        return {"message": "Provider B outage triggered — health set to 0.1"}

    elif scenario == "provider-restore":
        from app.providers.provider_b import ProviderB
        pb = providers.get("PROVIDER_B")
        if isinstance(pb, ProviderB):
            pb.restore()
        return {"message": "Provider B restored"}

    elif scenario == "agent-drop":
        # Sprint 4: set 40% of agents to OFFLINE
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.agent import Agent, AgentState

        if state.campaign_id:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    result = await db.execute(
                        select(Agent)
                        .where(Agent.campaign_id == state.campaign_id)
                        .where(Agent.state == AgentState.AVAILABLE)
                    )
                    agents = result.scalars().all()
                    drop_count = max(1, len(agents) // 2)
                    for agent in agents[:drop_count]:
                        agent.state = AgentState.OFFLINE
            return {"message": f"Dropped {drop_count} agents to OFFLINE"}
        return {"message": "No active campaign"}

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario: {scenario!r}. Valid: provider-outage, provider-restore, agent-drop",
        )


@router.get("/provider-health")
async def provider_health() -> dict:
    """Current health scores for all providers."""
    providers = get_all_providers()
    health = {}
    for name, p in providers.items():
        health[name] = await p.get_health_score()
    return health
