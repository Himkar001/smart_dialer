"""
Progressive & Predictive Dialer — core dialing logic.

Progressive mode: dial exactly N calls where N = available_agents (strict 1:1).
Predictive mode:  request more than N, route through Safety Controller,
                  use approved_count from pacing engine.

Both modes pass through the Safety Controller — no bypass is possible.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentState
from app.models.call import CallState
from app.models.campaign import Campaign, CampaignMode, CampaignState
from app.providers.base import TelecomProvider
from app.services.agent_state_machine import (
    count_available_agents,
    transition_agent,
)
from app.services.call_allocator import allocate_and_dial
from app.services.call_state_machine import count_calls_by_state, process_provider_event

logger = logging.getLogger(__name__)


def progressive_dial_count(available_agents: int, in_flight_calls: int) -> int:
    """
    Progressive mode: dial exactly as many calls as available agents.

    Strict 1:1 guarantee — no risk of abandoned calls.
    """
    return max(0, available_agents)


async def run_call_simulation(
    db: AsyncSession,
    call_id: uuid.UUID,
    agent_id: uuid.UUID,
    campaign_id: uuid.UUID,
    provider: TelecomProvider,
    answer_rate_override: float | None = None,
    mode: str = "PROGRESSIVE",
) -> None:
    """
    Background task: process all provider events for a single call.
    Records outcome in AnswerRateTracker after completion.
    """
    from sqlalchemy import select
    from app.models.agent import Agent
    from app.services.answer_rate_tracker import tracker as answer_tracker
    from app.database import AsyncSessionLocal

    answered = False
    logger.info("run_call_simulation: call %s starting event loop [%s]", call_id, provider.name)

    async with AsyncSessionLocal() as local_db:
        try:
            async for event_type, idempotency_key in provider.simulate_call_events(
                call_id, answer_rate_override
            ):
                async with local_db.begin():
                    await process_provider_event(local_db, call_id, event_type, idempotency_key)

                if event_type == "CONNECTED":
                    answered = True

            # Record outcome for answer rate tracker
            answer_tracker.record(str(campaign_id), answered)
            logger.debug(
                "run_call_simulation: call %s complete — answered=%s (tracker sample=%d)",
                call_id, answered, answer_tracker.get_sample_size(str(campaign_id)),
            )

        except Exception as e:
            logger.error("run_call_simulation: call %s ERROR: %s", call_id, e)
            answer_tracker.record(str(campaign_id), False)

        # Release agent
        try:
            async with local_db.begin():
                result = await local_db.execute(select(Agent).where(Agent.id == agent_id))
                agent = result.scalar_one_or_none()
                
                if agent and agent.state == AgentState.CONNECTED:
                    # If they connected, they get wrap-up time
                    await transition_agent(local_db, agent, AgentState.WRAP_UP)
                elif agent and agent.state == AgentState.DIALING:
                    # If they were just dialing (no answer), they go straight to available
                    await transition_agent(local_db, agent, AgentState.AVAILABLE)

            if answered:
                await asyncio.sleep(0.5)  # Simulate brief wrap-up time
                async with local_db.begin():
                    result = await local_db.execute(select(Agent).where(Agent.id == agent_id))
                    agent = result.scalar_one_or_none()
                    if agent and agent.state == AgentState.WRAP_UP:
                        await transition_agent(local_db, agent, AgentState.AVAILABLE)

            logger.debug("run_call_simulation: agent %s released to AVAILABLE", agent_id)

        except Exception as release_err:
            logger.error("run_call_simulation: failed to release agent %s: %s", agent_id, release_err)
            try:
                async with local_db.begin():
                    result = await local_db.execute(select(Agent).where(Agent.id == agent_id))
                    agent = result.scalar_one_or_none()
                    if agent and agent.state not in (AgentState.AVAILABLE, AgentState.OFFLINE):
                        await transition_agent(local_db, agent, AgentState.AVAILABLE)
            except Exception:
                pass


async def dialing_cycle(
    db: AsyncSession,
    campaign: Campaign,
    provider: TelecomProvider,
    answer_rate_override: float | None = None,
) -> dict:
    """
    Execute one dialing cycle for any mode: calculate → safety gate → allocate → simulate.

    Returns a summary dict with pacing decision details for the broadcaster.
    """
    from app.services.call_state_machine import count_calls_by_state
    from app.services.pacing_engine import compute_pacing_decision

    available = await count_available_agents(db, campaign.id)
    in_flight = await count_calls_by_state(
        db, campaign.id,
        [CallState.INITIATED, CallState.RINGING, CallState.ANSWERED, CallState.CONNECTED],
    )

    # Count completed + failed for abandoned rate
    completed = await count_calls_by_state(db, campaign.id, [CallState.COMPLETED])
    failed = await count_calls_by_state(db, campaign.id, [CallState.FAILED, CallState.CANCELLED])
    total_finished = completed + failed
    abandoned_rate = failed / total_finished if total_finished > 0 else 0.0

    # Provider health
    provider_health = await provider.get_health_score()

    # Compute pacing decision (pacing engine → safety controller)
    mode = campaign.mode.value if hasattr(campaign.mode, "value") else str(campaign.mode)
    decision = await compute_pacing_decision(
        campaign_id=campaign.id,
        available_agents=available,
        in_flight_calls=in_flight,
        provider_health=provider_health,
        abandoned_rate=abandoned_rate,
        mode=mode,
    )

    # Store last decision for broadcaster
    from app.services import _last_safety_decision_store
    _last_safety_decision_store["last"] = decision

    if decision.approved_count == 0:
        logger.debug("dialing_cycle: approved=0 (%s) — skipping", decision.action)
        return {
            "placed": 0, "decision": decision.action.value,
            "reason": decision.reason, "available": available,
        }

    # Allocate and launch simulations
    placed = 0
    
    # Clear implicit transaction from SELECTs (count_available_agents, etc)
    await db.commit()
    
    for _ in range(decision.approved_count):
        async with db.begin():
            result = await allocate_and_dial(db, campaign, provider, answer_rate_override)

        if result is None:
            break

        call, agent = result
        placed += 1

        asyncio.create_task(
            run_call_simulation(
                db, call.id, agent.id, campaign.id,
                provider, answer_rate_override, mode,
            ),
            name=f"call-sim-{call.id}",
        )

    logger.info(
        "dialing_cycle: campaign=%s mode=%s placed=%d/%d [%s]",
        campaign.id, mode, placed, decision.approved_count, decision.action,
    )
    return {
        "placed": placed,
        "decision": decision.action.value,
        "reason": decision.reason,
        "available": available,
        "requested": decision.requested_count,
        "approved": decision.approved_count,
    }


# Backwards-compat alias used by simulation_runner
async def progressive_dialing_cycle(
    db: AsyncSession,
    campaign: Campaign,
    provider: TelecomProvider,
    answer_rate_override: float | None = None,
) -> int:
    result = await dialing_cycle(db, campaign, provider, answer_rate_override)
    return result.get("placed", 0)
