"""Simulation control + failure scenario router."""

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.providers.registry import get_all_providers
from app.services.failure_scenarios import (
    SCENARIO_REGISTRY,
    incident_log,
    trigger_agent_drop,
    trigger_duplicate_storm,
    trigger_ooo_flood,
    trigger_provider_outage,
    trigger_worker_crash,
)
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
    # Clear incident log for fresh run
    incident_log.clear()
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
    Trigger one of 5 failure scenarios.

    Available scenarios:
      - provider-outage   : ProviderB health → 0.1, auto-recovers in 15s
      - worker-crash      : Cancel call tasks, stale agents auto-released in 3s
      - agent-drop        : 50% agents → OFFLINE, auto-restore in 20s
      - duplicate-storm   : 5 duplicate events per active call (all absorbed)
      - ooo-flood         : OOO COMPLETED events (all rejected by SM)
    """
    state = get_simulation_state()
    campaign_id = state.campaign_id

    if scenario not in SCENARIO_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario: '{scenario}'. Valid: {', '.join(SCENARIO_REGISTRY.keys())}",
        )

    # Scenarios requiring campaign_id
    if scenario in ("agent-drop", "duplicate-storm", "ooo-flood"):
        if not campaign_id:
            raise HTTPException(status_code=400, detail="No active simulation")

    if scenario == "provider-outage":
        return await trigger_provider_outage("PROVIDER_B")

    elif scenario == "worker-crash":
        return await trigger_worker_crash(campaign_id)

    elif scenario == "agent-drop":
        return await trigger_agent_drop(campaign_id)

    elif scenario == "duplicate-storm":
        return await trigger_duplicate_storm(campaign_id)

    elif scenario == "ooo-flood":
        return await trigger_ooo_flood(campaign_id)

    raise HTTPException(status_code=500, detail="Scenario handler not found")


@router.get("/incidents")
async def get_incidents() -> list[dict]:
    """Return the incident timeline for the current simulation run."""
    return [asdict(entry) for entry in incident_log]


@router.get("/provider-health")
async def provider_health() -> dict:
    """Current health scores for all providers."""
    providers = get_all_providers()
    return {name: await p.get_health_score() for name, p in providers.items()}
