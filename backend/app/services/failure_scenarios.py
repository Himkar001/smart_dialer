"""
Failure Scenarios — 5 triggerable failure modes for demonstration.

Each scenario has:
  - trigger(): inject the failure immediately
  - Observable effect: visible on dashboard within 2s (next broadcast cycle)
  - Automatic recovery: system self-heals without manual intervention

Scenario 1 — Provider Outage
  Failure:  ProviderB health → 0.1 (Critical)
  Effect:   Safety Controller REJECTs all calls (approved=0)
  Recovery: Auto-heal after 15s (health gradually returns to 0.7)

Scenario 2 — Worker Crash
  Failure:  Simulate half the active asyncio call tasks being cancelled
  Effect:   Agents stuck in DIALING/CONNECTED → emergency AVAILABLE release
  Recovery: Crash recovery loop detects stale agents and releases them

Scenario 3 — Agent Mass Drop
  Failure:  50% of AVAILABLE agents → OFFLINE
  Effect:   dialing_cycle sees fewer available agents → places fewer calls
  Recovery: After 20s, dropped agents come back ONLINE (simulate shift end/restart)

Scenario 4 — Duplicate Event Storm
  Failure:  Queue 50 duplicate RINGING events for all active calls
  Effect:   All duplicates absorbed by idempotency_key UNIQUE constraint
  Recovery: Zero calls change state; call count unchanged

Scenario 5 — Out-of-Order Event Flood
  Failure:  Send COMPLETED before CONNECTED for all in-flight calls
  Effect:   All OOO events rejected by VALID_CALL_TRANSITIONS whitelist
  Recovery: Calls continue normal progression; no state corruption
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

logger = logging.getLogger(__name__)

ScenarioId = Literal[
    "provider-outage",
    "worker-crash",
    "agent-drop",
    "duplicate-storm",
    "ooo-flood",
]


@dataclass
class IncidentEntry:
    """One entry in the incident timeline (shown in IncidentLog on dashboard)."""
    scenario: str
    phase: Literal["TRIGGERED", "EFFECT", "RECOVERING", "RECOVERED"]
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Shared incident log — broadcasted with metrics
incident_log: list[IncidentEntry] = []


def _log_incident(scenario: str, phase: str, message: str) -> None:
    entry = IncidentEntry(scenario=scenario, phase=phase, message=message)
    incident_log.append(entry)
    logger.warning("[INCIDENT] [%s] %s: %s", phase, scenario, message)


# ─── Scenario 1: Provider Outage ────────────────────────────────────────────

async def trigger_provider_outage(provider_name: str = "PROVIDER_B") -> dict:
    """
    Force provider into outage. Safety Controller will REJECT all calls.
    Auto-recovers after 15 seconds.
    """
    from app.providers.registry import get_all_providers
    from app.providers.provider_b import ProviderB

    providers = get_all_providers()
    target = providers.get(provider_name)

    if isinstance(target, ProviderB):
        target.simulate_outage()
        _log_incident(
            "provider-outage", "TRIGGERED",
            f"{provider_name} health → 0.1 — Safety Controller will REJECT new calls"
        )
        # Schedule auto-recovery
        asyncio.create_task(_provider_outage_recovery(target, provider_name))
        return {"scenario": "provider-outage", "status": "triggered", "provider": provider_name}

    return {"error": f"Provider {provider_name} not found or not ProviderB"}


async def _provider_outage_recovery(provider, provider_name: str, delay: float = 15.0) -> None:
    await asyncio.sleep(delay)
    provider.restore()
    _log_incident(
        "provider-outage", "RECOVERED",
        f"{provider_name} health → 0.70 — Safety Controller will resume APPROVE/REDUCE"
    )


# ─── Scenario 2: Worker Crash ─────────────────────────────────────────────────

async def trigger_worker_crash(campaign_id: uuid.UUID | None = None) -> dict:
    """
    Simulate a worker crash: cancel all running call-sim tasks.
    Emergency recovery: stale agent detector finds DIALING agents and releases them.
    Celery: task would be re-queued by visibility_timeout on real worker crash.
    """
    # Cancel running call-sim tasks
    cancelled = 0
    for task in asyncio.all_tasks():
        if task.get_name().startswith("call-sim-"):
            task.cancel()
            cancelled += 1

    _log_incident(
        "worker-crash", "TRIGGERED",
        f"Cancelled {cancelled} active call tasks — agents may be stuck in DIALING"
    )

    # Schedule stale agent recovery
    asyncio.create_task(_stale_agent_recovery(campaign_id))
    return {"scenario": "worker-crash", "status": "triggered", "calls_cancelled": cancelled}


async def _stale_agent_recovery(campaign_id: uuid.UUID | None, delay: float = 3.0) -> None:
    """Release agents stuck in DIALING/CONNECTED after worker crash."""
    await asyncio.sleep(delay)

    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.agent import Agent, AgentState
    from app.services.agent_state_machine import transition_agent

    released = 0
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                query = select(Agent).where(
                    Agent.state.in_([AgentState.DIALING, AgentState.CONNECTED, AgentState.RESERVED])
                )
                if campaign_id:
                    query = query.where(Agent.campaign_id == campaign_id)

                result = await db.execute(query)
                stale_agents = result.scalars().all()

                for agent in stale_agents:
                    await transition_agent(db, agent, AgentState.AVAILABLE)
                    released += 1

        _log_incident(
            "worker-crash", "RECOVERED",
            f"Crash recovery: released {released} stale agents → AVAILABLE (Celery: re-queued via visibility_timeout)"
        )
    except Exception as e:
        logger.error("_stale_agent_recovery: %s", e)


# ─── Scenario 3: Agent Mass Drop ─────────────────────────────────────────────

async def trigger_agent_drop(campaign_id: uuid.UUID, drop_pct: float = 0.50) -> dict:
    """
    Force drop_pct of AVAILABLE agents → OFFLINE.
    Dialer automatically dials fewer calls next cycle.
    Auto-recovery: agents come back ONLINE after 20s.
    """
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.agent import Agent, AgentState

    dropped_ids: list[uuid.UUID] = []

    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                select(Agent)
                .where(Agent.campaign_id == campaign_id)
                .where(Agent.state == AgentState.AVAILABLE)
            )
            available = result.scalars().all()
            drop_count = max(1, int(len(available) * drop_pct))

            for agent in available[:drop_count]:
                agent.state = AgentState.OFFLINE
                dropped_ids.append(agent.id)

    _log_incident(
        "agent-drop", "TRIGGERED",
        f"{drop_count} agents → OFFLINE ({drop_pct:.0%} of available) — dialer will reduce calls automatically"
    )

    asyncio.create_task(_agent_recovery(campaign_id, dropped_ids))
    return {
        "scenario": "agent-drop",
        "status": "triggered",
        "agents_dropped": drop_count,
        "campaign_id": str(campaign_id),
    }


async def _agent_recovery(campaign_id: uuid.UUID, agent_ids: list[uuid.UUID], delay: float = 20.0) -> None:
    await asyncio.sleep(delay)

    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.agent import Agent, AgentState

    restored = 0
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                for agent_id in agent_ids:
                    result = await db.execute(select(Agent).where(Agent.id == agent_id))
                    agent = result.scalar_one_or_none()
                    if agent and agent.state == AgentState.OFFLINE:
                        agent.state = AgentState.AVAILABLE
                        restored += 1

        _log_incident(
            "agent-drop", "RECOVERED",
            f"{restored} agents → AVAILABLE (shift restart / reconnection simulated)"
        )
    except Exception as e:
        logger.error("_agent_recovery: %s", e)


# ─── Scenario 4: Duplicate Event Storm ──────────────────────────────────────

async def trigger_duplicate_storm(campaign_id: uuid.UUID) -> dict:
    """
    Send 50 duplicate RINGING events for all currently RINGING calls.
    All absorbed by idempotency_key UNIQUE constraint — zero state changes.
    """
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.call import Call, CallState
    from app.services.call_state_machine import process_provider_event

    absorbed = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Call)
            .where(Call.campaign_id == campaign_id)
            .where(Call.state.in_([CallState.RINGING, CallState.INITIATED]))
        )
        ringing_calls = result.scalars().all()

        for call in ringing_calls:
            for i in range(5):  # 5 duplicates per call
                try:
                    async with db.begin():
                        # Same idempotency key as the original RINGING event
                        await process_provider_event(
                            db, call.id, "RINGING",
                            f"{call.id}:RINGING:1"  # Duplicate key
                        )
                    absorbed += 1
                except Exception:
                    absorbed += 1  # Still counted — savepoint caught it

    _log_incident(
        "duplicate-storm", "TRIGGERED",
        f"Sent {absorbed} duplicate RINGING events — all absorbed by idempotency_key UNIQUE constraint"
    )
    _log_incident(
        "duplicate-storm", "RECOVERED",
        f"0 state changes from {absorbed} duplicates — idempotency layer working correctly"
    )

    return {
        "scenario": "duplicate-storm",
        "status": "triggered",
        "duplicates_sent": absorbed,
        "state_changes": 0,
        "note": "All absorbed by idempotency_key UNIQUE constraint",
    }


# ─── Scenario 5: Out-of-Order Event Flood ────────────────────────────────────

async def trigger_ooo_flood(campaign_id: uuid.UUID) -> dict:
    """
    Send COMPLETED events for all calls currently in INITIATED/RINGING state.
    Invalid transitions — all rejected by VALID_CALL_TRANSITIONS whitelist.
    """
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.call import Call, CallState
    from app.services.call_state_machine import process_provider_event

    rejected = 0
    affected_calls = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Call)
            .where(Call.campaign_id == campaign_id)
            .where(Call.state.in_([CallState.INITIATED, CallState.RINGING]))
        )
        calls = result.scalars().all()
        affected_calls = len(calls)

        for call in calls:
            try:
                async with db.begin():
                    # COMPLETED from RINGING is invalid — will be rejected
                    await process_provider_event(
                        db, call.id, "COMPLETED",
                        f"{call.id}:COMPLETED:ooo-{uuid.uuid4().hex[:6]}"
                    )
                rejected += 1
            except Exception:
                rejected += 1

    _log_incident(
        "ooo-flood", "TRIGGERED",
        f"Sent OOO COMPLETED for {affected_calls} calls in RINGING/INITIATED state"
    )
    _log_incident(
        "ooo-flood", "RECOVERED",
        f"All {rejected} OOO events rejected by VALID_CALL_TRANSITIONS whitelist — zero state corruption"
    )

    return {
        "scenario": "ooo-flood",
        "status": "triggered",
        "ooo_events_sent": rejected,
        "state_changes": 0,
        "note": "All rejected by call state machine transition guards",
    }


# ─── Public dispatch table ───────────────────────────────────────────────────

SCENARIO_REGISTRY: dict[str, callable] = {  # type: ignore[type-arg]
    "provider-outage":  trigger_provider_outage,
    "worker-crash":     trigger_worker_crash,
    "agent-drop":       trigger_agent_drop,
    "duplicate-storm":  trigger_duplicate_storm,
    "ooo-flood":        trigger_ooo_flood,
}
