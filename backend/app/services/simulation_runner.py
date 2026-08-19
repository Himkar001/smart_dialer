"""
Simulation Runner — manages the lifecycle of a running dialing simulation.

Runs entirely within the FastAPI process using asyncio background tasks.
No Celery required for Sprint 2 (Celery architecture is documented for
distributed deployment; the simulation runner shows the same logic).
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.database import AsyncSessionLocal
from app.models.agent import Agent, AgentState
from app.models.borrower import Borrower, BorrowerState
from app.models.campaign import Campaign, CampaignMode, CampaignState, ProviderType

logger = logging.getLogger(__name__)

IN_FLIGHT_STATES = None  # imported lazily to avoid circular imports


@dataclass
class SimulationState:
    """Tracks the currently running simulation."""
    campaign_id: uuid.UUID | None = None
    is_running: bool = False
    started_at: datetime | None = None
    provider_type: str = "PROVIDER_A"
    mode: str = "PROGRESSIVE"
    answer_rate_override: float | None = None
    _task: asyncio.Task | None = field(default=None, repr=False)


# Global singleton — only one simulation runs at a time for this prototype
_sim_state = SimulationState()


def get_simulation_state() -> SimulationState:
    return _sim_state


async def _seed_campaign(
    agent_count: int,
    borrower_count: int,
    mode: CampaignMode,
    provider: ProviderType,
) -> uuid.UUID:
    """Create a campaign with agents and borrowers in the DB."""
    async with AsyncSessionLocal() as db:
        async with db.begin():
            campaign = Campaign(
                name=f"Simulation {datetime.now(timezone.utc).strftime('%H:%M:%S')}",
                mode=mode,
                state=CampaignState.ACTIVE,
                provider=provider,
                max_retries=2,
            )
            db.add(campaign)
            await db.flush()  # Get campaign.id

            agents = [
                Agent(
                    name=f"Agent {i+1}",
                    state=AgentState.AVAILABLE,
                    campaign_id=campaign.id,
                )
                for i in range(agent_count)
            ]
            borrowers = [
                Borrower(
                    name=f"Borrower {i+1}",
                    phone=f"+1555{1000000 + i:07d}",
                    campaign_id=campaign.id,
                    state=BorrowerState.PENDING,
                )
                for i in range(borrower_count)
            ]
            db.add_all(agents)
            db.add_all(borrowers)

        logger.info(
            "Seeded campaign %s: %d agents, %d borrowers",
            campaign.id, agent_count, borrower_count,
        )
        return campaign.id


async def _dialing_loop(
    campaign_id: uuid.UUID,
    answer_rate_override: float | None,
) -> None:
    """Main dialing loop — runs until campaign is stopped or borrowers exhausted."""
    from sqlalchemy import select
    from app.models.borrower import BorrowerState
    from app.providers.registry import get_provider
    from app.services.dialer import progressive_dialing_cycle

    logger.info("Dialing loop started for campaign %s", campaign_id)

    while _sim_state.is_running:
        try:
            async with AsyncSessionLocal() as db:
                # Load campaign
                result = await db.execute(
                    select(Campaign).where(Campaign.id == campaign_id)
                )
                campaign = result.scalar_one_or_none()
                if campaign is None or campaign.state != CampaignState.ACTIVE:
                    logger.info("Campaign %s no longer active — stopping loop", campaign_id)
                    break

                # Check if any borrowers remain
                pending_count_result = await db.execute(
                    select(Borrower)
                    .where(Borrower.campaign_id == campaign_id)
                    .where(Borrower.state == BorrowerState.PENDING)
                    .limit(1)
                )
                if pending_count_result.scalar_one_or_none() is None:
                    logger.info("All borrowers exhausted for campaign %s", campaign_id)
                    break

                provider = get_provider(campaign.provider)
                
                # Clear the implicit transaction from the SELECTs above
                # so that dialing_cycle can manage its own db.begin() blocks
                await db.commit()
                
                await progressive_dialing_cycle(db, campaign, provider, answer_rate_override)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Dialing loop error: %s", e)

        await asyncio.sleep(2)  # Pacing cycle every 2 seconds

    _sim_state.is_running = False
    logger.info("Dialing loop ended for campaign %s", campaign_id)


async def start_simulation(
    agent_count: int,
    borrower_count: int,
    mode: str = "PROGRESSIVE",
    provider_type: str = "PROVIDER_A",
    answer_rate_override: float | None = None,
) -> uuid.UUID:
    """Seed DB and launch the dialing loop as a background task."""
    global _sim_state

    if _sim_state.is_running:
        await stop_simulation()

    campaign_id = await _seed_campaign(
        agent_count=agent_count,
        borrower_count=borrower_count,
        mode=CampaignMode(mode),
        provider=ProviderType(provider_type),
    )

    _sim_state.campaign_id = campaign_id
    _sim_state.is_running = True
    _sim_state.started_at = datetime.now(timezone.utc)
    _sim_state.provider_type = provider_type
    _sim_state.mode = mode
    _sim_state.answer_rate_override = answer_rate_override

    _sim_state._task = asyncio.create_task(
        _dialing_loop(campaign_id, answer_rate_override),
        name="dialing-loop",
    )
    logger.info(
        "Simulation started: campaign=%s agents=%d borrowers=%d mode=%s provider=%s",
        campaign_id, agent_count, borrower_count, mode, provider_type,
    )
    return campaign_id


async def stop_simulation() -> None:
    """Stop the running simulation gracefully."""
    global _sim_state
    _sim_state.is_running = False

    if _sim_state._task and not _sim_state._task.done():
        _sim_state._task.cancel()
        try:
            await asyncio.wait_for(_sim_state._task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    # Mark campaign as completed
    if _sim_state.campaign_id:
        try:
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    result = await db.execute(
                        select(Campaign).where(Campaign.id == _sim_state.campaign_id)
                    )
                    campaign = result.scalar_one_or_none()
                    if campaign:
                        campaign.state = CampaignState.COMPLETED
        except Exception as e:
            logger.error("stop_simulation: failed to mark campaign completed: %s", e)

    logger.info("Simulation stopped (campaign=%s)", _sim_state.campaign_id)
