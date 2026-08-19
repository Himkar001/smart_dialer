"""
Agent State Machine

Key design decisions:
1. reserve_agent() uses SELECT FOR UPDATE SKIP LOCKED — the only safe way to prevent
   two Celery workers from reserving the same agent simultaneously.
   SKIP LOCKED means competing workers skip already-locked rows instead of waiting,
   so each gets a different agent with no deadlock risk.

2. transition_agent() enforces a strict allow-list of valid transitions.
   Any invalid transition raises InvalidTransitionError, which callers must handle.

3. All state changes go through this module — no direct ORM field mutations elsewhere.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentState

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Valid state transitions — only these are permitted
# ------------------------------------------------------------------
VALID_AGENT_TRANSITIONS: dict[AgentState, list[AgentState]] = {
    AgentState.OFFLINE:    [AgentState.AVAILABLE],
    AgentState.AVAILABLE:  [AgentState.RESERVED, AgentState.PAUSED],
    AgentState.RESERVED:   [AgentState.DIALING, AgentState.AVAILABLE],
    AgentState.DIALING:    [AgentState.CONNECTED, AgentState.AVAILABLE],
    AgentState.CONNECTED:  [AgentState.WRAP_UP, AgentState.OFFLINE],
    AgentState.WRAP_UP:    [AgentState.AVAILABLE, AgentState.PAUSED],
    AgentState.PAUSED:     [AgentState.AVAILABLE, AgentState.OFFLINE],
}


class InvalidTransitionError(Exception):
    """Raised when an illegal agent state transition is attempted."""
    pass


async def reserve_agent(db: AsyncSession, campaign_id: uuid.UUID) -> Agent | None:
    """
    Atomically reserve one AVAILABLE agent for a campaign.

    On PostgreSQL (production): SELECT FOR UPDATE SKIP LOCKED prevents
    two workers from ever reserving the same agent simultaneously.

    On SQLite (unit tests): falls back to plain SELECT since SQLite
    doesn't support row-level locking. The production guarantee is
    enforced at the PostgreSQL level.

    Returns:
        The reserved Agent, or None if no agents are available.
    """
    query = (
        select(Agent)
        .where(Agent.state == AgentState.AVAILABLE)
        .where(Agent.campaign_id == campaign_id)
        .limit(1)
    )
    # Apply PostgreSQL-specific locking only when connected to PostgreSQL
    try:
        dialect = db.get_bind().dialect.name  # type: ignore[attr-defined]
    except Exception:
        dialect = "sqlite"

    if dialect == "postgresql":
        query = query.with_for_update(skip_locked=True)

    result = await db.execute(query)
    agent = result.scalar_one_or_none()

    if agent is None:
        logger.debug("reserve_agent: no available agents for campaign %s", campaign_id)
        return None

    now = datetime.now(timezone.utc)
    agent.state = AgentState.RESERVED
    agent.reserved_at = now
    agent.heartbeat_at = now
    agent.updated_at = now

    logger.info("reserve_agent: reserved agent %s for campaign %s", agent.id, campaign_id)
    return agent


async def transition_agent(
    db: AsyncSession,
    agent: Agent,
    to_state: AgentState,
) -> Agent:
    """
    Transition an agent to a new state, enforcing the allow-list.

    Args:
        db: Active async session.
        agent: The agent to transition.
        to_state: Target state.

    Returns:
        The updated agent.

    Raises:
        InvalidTransitionError: If the transition is not allowed.
    """
    allowed = VALID_AGENT_TRANSITIONS.get(agent.state, [])
    if to_state not in allowed:
        raise InvalidTransitionError(
            f"Agent {agent.id}: transition {agent.state} → {to_state} is not allowed. "
            f"Valid targets: {[s.value for s in allowed]}"
        )

    old_state = agent.state
    agent.state = to_state
    agent.updated_at = datetime.now(timezone.utc)

    # Clear reserved_at when releasing back to available
    if to_state == AgentState.AVAILABLE:
        agent.reserved_at = None

    await db.flush()

    logger.info(
        "transition_agent: agent %s  %s → %s",
        agent.id, old_state.value, to_state.value
    )
    return agent


async def release_agent(db: AsyncSession, agent: Agent) -> Agent:
    """
    Convenience: release a reserved/dialing agent back to AVAILABLE.
    Used during error recovery and worker crash cleanup.
    """
    if agent.state in (AgentState.RESERVED, AgentState.DIALING, AgentState.CONNECTED):
        return await transition_agent(db, agent, AgentState.AVAILABLE)
    logger.warning(
        "release_agent: agent %s is in state %s, cannot release", agent.id, agent.state
    )
    return agent


async def get_agent(db: AsyncSession, agent_id: uuid.UUID) -> Agent | None:
    """Fetch a single agent by ID."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    return result.scalar_one_or_none()


async def count_available_agents(db: AsyncSession, campaign_id: uuid.UUID) -> int:
    """Return the count of AVAILABLE agents for a campaign."""
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(Agent.id))
        .where(Agent.state == AgentState.AVAILABLE)
        .where(Agent.campaign_id == campaign_id)
    )
    return result.scalar_one() or 0
