"""
Progressive Dialer — core dialing logic.

Progressive mode: dial exactly N calls where N = number of AVAILABLE agents.
This is the strict 1:1 guarantee — zero risk of abandoned calls.

Architecture note: This module contains pure dialing logic.
It is called by the simulation runner, which handles DB session lifecycle.
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
    Progressive mode: dial exactly as many calls as there are available agents.

    Args:
        available_agents: Agents currently in AVAILABLE state.
        in_flight_calls: Calls currently INITIATED/RINGING/ANSWERED/CONNECTED.

    Returns:
        Number of new calls to place. Always >= 0.

    The strict invariant: total_active_calls <= total_agent_capacity.
    We only place calls for agents that are free RIGHT NOW.
    """
    to_dial = max(0, available_agents)
    logger.debug(
        "progressive_dial_count: available=%d in_flight=%d → dial=%d",
        available_agents, in_flight_calls, to_dial,
    )
    return to_dial


async def run_call_simulation(
    db: AsyncSession,
    call_id: uuid.UUID,
    agent_id: uuid.UUID,
    provider: TelecomProvider,
    answer_rate_override: float | None = None,
) -> None:
    """
    Background task: process all provider events for a single call to completion.
    Updates call state machine and releases the agent when done.
    """
    from sqlalchemy import select
    from app.models.agent import Agent
    from app.models.call import Call

    logger.info("run_call_simulation: call %s starting event loop", call_id)

    try:
        async for event_type, idempotency_key in provider.simulate_call_events(
            call_id, answer_rate_override
        ):
            async with db.begin():
                await process_provider_event(db, call_id, event_type, idempotency_key)

        # Call complete — transition agent to WRAP_UP then AVAILABLE
        async with db.begin():
            result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            if agent and agent.state in (AgentState.DIALING, AgentState.CONNECTED):
                await transition_agent(db, agent, AgentState.WRAP_UP)

        await asyncio.sleep(0.5)  # Brief wrap-up

        async with db.begin():
            result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            if agent and agent.state == AgentState.WRAP_UP:
                await transition_agent(db, agent, AgentState.AVAILABLE)

        logger.info("run_call_simulation: call %s complete, agent %s released", call_id, agent_id)

    except Exception as e:
        logger.error("run_call_simulation: call %s ERROR: %s", call_id, e)
        # Emergency release — get agent back to AVAILABLE
        try:
            async with db.begin():
                result = await db.execute(select(Agent).where(Agent.id == agent_id))
                agent = result.scalar_one_or_none()
                if agent and agent.state not in (AgentState.AVAILABLE, AgentState.OFFLINE):
                    await transition_agent(db, agent, AgentState.AVAILABLE)
        except Exception as release_err:
            logger.error("run_call_simulation: failed to release agent %s: %s", agent_id, release_err)


async def progressive_dialing_cycle(
    db: AsyncSession,
    campaign: Campaign,
    provider: TelecomProvider,
    answer_rate_override: float | None = None,
) -> int:
    """
    Execute one progressive dialing cycle: calculate → allocate → launch simulations.

    Returns the number of calls placed this cycle.
    """
    available = await count_available_agents(db, campaign.id)
    in_flight = await count_calls_by_state(
        db, campaign.id,
        [CallState.INITIATED, CallState.RINGING, CallState.ANSWERED, CallState.CONNECTED]
    )

    to_dial = progressive_dial_count(available, in_flight)

    if to_dial == 0:
        logger.debug("progressive_dialing_cycle: nothing to dial (available=%d)", available)
        return 0

    placed = 0
    tasks = []

    for _ in range(to_dial):
        async with db.begin():
            result = await allocate_and_dial(db, campaign, provider, answer_rate_override)

        if result is None:
            break  # No more resources

        call, agent = result
        placed += 1

        # Launch call simulation as background task
        task = asyncio.create_task(
            run_call_simulation(db, call.id, agent.id, provider, answer_rate_override),
            name=f"call-sim-{call.id}",
        )
        tasks.append(task)

    logger.info(
        "progressive_dialing_cycle: campaign=%s placed=%d/%d calls",
        campaign.id, placed, to_dial,
    )
    return placed
