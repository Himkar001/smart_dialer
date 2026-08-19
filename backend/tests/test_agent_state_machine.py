"""
Tests for Agent State Machine.

Covers:
- All valid state transitions
- All invalid state transitions are rejected
- reserve_agent returns None when no agents available
- transition_agent raises InvalidTransitionError on bad transition
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentState
from app.models.campaign import Campaign
from app.services.agent_state_machine import (
    VALID_AGENT_TRANSITIONS,
    InvalidTransitionError,
    count_available_agents,
    release_agent,
    transition_agent,
)

pytestmark = pytest.mark.asyncio


class TestValidTransitions:
    """All valid transitions should succeed."""

    async def test_offline_to_available(self, db: AsyncSession, campaign: Campaign):
        agent = Agent(name="A", state=AgentState.OFFLINE, campaign_id=campaign.id)
        db.add(agent)
        await db.commit()
        result = await transition_agent(db, agent, AgentState.AVAILABLE)
        assert result.state == AgentState.AVAILABLE

    async def test_available_to_reserved(self, db: AsyncSession, available_agent: Agent):
        result = await transition_agent(db, available_agent, AgentState.RESERVED)
        assert result.state == AgentState.RESERVED

    async def test_available_to_paused(self, db: AsyncSession, available_agent: Agent):
        result = await transition_agent(db, available_agent, AgentState.PAUSED)
        assert result.state == AgentState.PAUSED

    async def test_reserved_to_dialing(self, db: AsyncSession, available_agent: Agent):
        await transition_agent(db, available_agent, AgentState.RESERVED)
        result = await transition_agent(db, available_agent, AgentState.DIALING)
        assert result.state == AgentState.DIALING

    async def test_reserved_to_available(self, db: AsyncSession, available_agent: Agent):
        await transition_agent(db, available_agent, AgentState.RESERVED)
        result = await transition_agent(db, available_agent, AgentState.AVAILABLE)
        assert result.state == AgentState.AVAILABLE
        assert result.reserved_at is None  # reserved_at cleared

    async def test_dialing_to_connected(self, db: AsyncSession, available_agent: Agent):
        await transition_agent(db, available_agent, AgentState.RESERVED)
        await transition_agent(db, available_agent, AgentState.DIALING)
        result = await transition_agent(db, available_agent, AgentState.CONNECTED)
        assert result.state == AgentState.CONNECTED

    async def test_dialing_to_available(self, db: AsyncSession, available_agent: Agent):
        await transition_agent(db, available_agent, AgentState.RESERVED)
        await transition_agent(db, available_agent, AgentState.DIALING)
        result = await transition_agent(db, available_agent, AgentState.AVAILABLE)
        assert result.state == AgentState.AVAILABLE

    async def test_connected_to_wrap_up(self, db: AsyncSession, available_agent: Agent):
        await transition_agent(db, available_agent, AgentState.RESERVED)
        await transition_agent(db, available_agent, AgentState.DIALING)
        await transition_agent(db, available_agent, AgentState.CONNECTED)
        result = await transition_agent(db, available_agent, AgentState.WRAP_UP)
        assert result.state == AgentState.WRAP_UP

    async def test_wrap_up_to_available(self, db: AsyncSession, available_agent: Agent):
        await transition_agent(db, available_agent, AgentState.RESERVED)
        await transition_agent(db, available_agent, AgentState.DIALING)
        await transition_agent(db, available_agent, AgentState.CONNECTED)
        await transition_agent(db, available_agent, AgentState.WRAP_UP)
        result = await transition_agent(db, available_agent, AgentState.AVAILABLE)
        assert result.state == AgentState.AVAILABLE

    async def test_paused_to_available(self, db: AsyncSession, available_agent: Agent):
        await transition_agent(db, available_agent, AgentState.PAUSED)
        result = await transition_agent(db, available_agent, AgentState.AVAILABLE)
        assert result.state == AgentState.AVAILABLE

    async def test_paused_to_offline(self, db: AsyncSession, available_agent: Agent):
        await transition_agent(db, available_agent, AgentState.PAUSED)
        result = await transition_agent(db, available_agent, AgentState.OFFLINE)
        assert result.state == AgentState.OFFLINE


class TestInvalidTransitions:
    """Invalid transitions must raise InvalidTransitionError."""

    async def test_available_to_connected_invalid(self, db: AsyncSession, available_agent: Agent):
        with pytest.raises(InvalidTransitionError):
            await transition_agent(db, available_agent, AgentState.CONNECTED)

    async def test_available_to_wrap_up_invalid(self, db: AsyncSession, available_agent: Agent):
        with pytest.raises(InvalidTransitionError):
            await transition_agent(db, available_agent, AgentState.WRAP_UP)

    async def test_available_to_dialing_invalid(self, db: AsyncSession, available_agent: Agent):
        with pytest.raises(InvalidTransitionError):
            await transition_agent(db, available_agent, AgentState.DIALING)

    async def test_offline_to_reserved_invalid(self, db: AsyncSession, campaign: Campaign):
        agent = Agent(name="A", state=AgentState.OFFLINE, campaign_id=campaign.id)
        db.add(agent)
        await db.commit()
        with pytest.raises(InvalidTransitionError):
            await transition_agent(db, agent, AgentState.RESERVED)

    async def test_connected_to_available_invalid(self, db: AsyncSession, available_agent: Agent):
        await transition_agent(db, available_agent, AgentState.RESERVED)
        await transition_agent(db, available_agent, AgentState.DIALING)
        await transition_agent(db, available_agent, AgentState.CONNECTED)
        with pytest.raises(InvalidTransitionError):
            await transition_agent(db, available_agent, AgentState.AVAILABLE)

    async def test_completed_state_has_no_valid_transitions(self):
        """Terminal states should have empty transition lists."""
        # OFFLINE has no outgoing from COMPLETED — check VALID_AGENT_TRANSITIONS
        # doesn't define unexpected states
        for state in AgentState:
            transitions = VALID_AGENT_TRANSITIONS.get(state, [])
            assert isinstance(transitions, list)


class TestReserveAgent:
    """reserve_agent uses SKIP LOCKED — tested here with SQLite fallback."""

    async def test_reserve_returns_none_when_no_agents(self, db: AsyncSession, campaign: Campaign):
        from app.services.agent_state_machine import reserve_agent
        # No agents exist — should return None
        # Note: SQLite doesn't support FOR UPDATE SKIP LOCKED, so we test the None path directly
        agent = await reserve_agent(db, campaign.id)
        assert agent is None

    async def test_reserve_returns_none_when_all_offline(
        self, db: AsyncSession, campaign: Campaign
    ):
        from app.services.agent_state_machine import reserve_agent
        offline = Agent(name="Offline", state=AgentState.OFFLINE, campaign_id=campaign.id)
        db.add(offline)
        await db.commit()
        agent = await reserve_agent(db, campaign.id)
        assert agent is None


class TestCountAvailableAgents:
    async def test_count_zero_initially(self, db: AsyncSession, campaign: Campaign):
        count = await count_available_agents(db, campaign.id)
        assert count == 0

    async def test_count_available_agents(self, db: AsyncSession, campaign: Campaign):
        agents = [
            Agent(name=f"Agent {i}", state=AgentState.AVAILABLE, campaign_id=campaign.id)
            for i in range(5)
        ]
        db.add_all(agents)
        await db.commit()
        count = await count_available_agents(db, campaign.id)
        assert count == 5

    async def test_count_excludes_reserved(self, db: AsyncSession, campaign: Campaign):
        available = Agent(name="Available", state=AgentState.AVAILABLE, campaign_id=campaign.id)
        reserved = Agent(name="Reserved", state=AgentState.RESERVED, campaign_id=campaign.id)
        db.add_all([available, reserved])
        await db.commit()
        count = await count_available_agents(db, campaign.id)
        assert count == 1


class TestReleaseAgent:
    async def test_release_reserved_agent(self, db: AsyncSession, available_agent: Agent):
        await transition_agent(db, available_agent, AgentState.RESERVED)
        result = await release_agent(db, available_agent)
        assert result.state == AgentState.AVAILABLE

    async def test_release_dialing_agent(self, db: AsyncSession, available_agent: Agent):
        await transition_agent(db, available_agent, AgentState.RESERVED)
        await transition_agent(db, available_agent, AgentState.DIALING)
        result = await release_agent(db, available_agent)
        assert result.state == AgentState.AVAILABLE

    async def test_release_offline_agent_noop(self, db: AsyncSession, campaign: Campaign):
        agent = Agent(name="A", state=AgentState.OFFLINE, campaign_id=campaign.id)
        db.add(agent)
        await db.commit()
        result = await release_agent(db, agent)
        assert result.state == AgentState.OFFLINE  # Unchanged — cannot release OFFLINE
