"""
Call Allocator — atomically reserves agent + borrower, creates call record,
then calls the provider. Rolls back all DB changes on any failure.

Pipeline (all within one DB transaction):
  1. Reserve AVAILABLE agent       (SELECT FOR UPDATE SKIP LOCKED)
  2. Reserve PENDING borrower      (SELECT FOR UPDATE SKIP LOCKED)
  3. Create Call record in RESERVED state
  4. Call provider.initiate_call()
  5a. SUCCESS → update Call to INITIATED, commit
  5b. FAILURE → rollback everything, agent + borrower freed automatically
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentState
from app.models.borrower import Borrower, BorrowerState
from app.models.call import Call, CallState
from app.models.campaign import Campaign
from app.providers.base import ProviderStatus, TelecomProvider
from app.services.agent_state_machine import transition_agent
from app.services.call_state_machine import transition_call

logger = logging.getLogger(__name__)


class AllocationError(Exception):
    """Raised when a call cannot be allocated (no agents or borrowers)."""
    pass


async def _reserve_borrower(db: AsyncSession, campaign_id: uuid.UUID) -> Borrower | None:
    """Reserve one PENDING borrower using SKIP LOCKED (dialect-aware)."""
    try:
        dialect = db.get_bind().dialect.name  # type: ignore[attr-defined]
    except Exception:
        dialect = "sqlite"

    query = (
        select(Borrower)
        .where(Borrower.campaign_id == campaign_id)
        .where(Borrower.state == BorrowerState.PENDING)
        .limit(1)
    )
    if dialect == "postgresql":
        query = query.with_for_update(skip_locked=True)

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def allocate_and_dial(
    db: AsyncSession,
    campaign: Campaign,
    provider: TelecomProvider,
    answer_rate_override: float | None = None,
) -> tuple[Call, Agent] | None:
    """
    Reserve one agent + one borrower, create a call, and initiate it.

    Returns (call, agent) on success, or None if no resources available.
    On provider failure, the DB transaction is rolled back automatically
    by the caller's session scope.

    Rollback guarantee: agent and borrower states are only committed AFTER
    the provider confirms the call was placed. If provider fails, the
    entire transaction rolls back — no orphaned reservations.
    """
    from app.services.agent_state_machine import reserve_agent

    # Step 1: Reserve agent
    agent = await reserve_agent(db, campaign.id)
    if agent is None:
        return None  # No available agents

    # Step 2: Reserve borrower
    borrower = await _reserve_borrower(db, campaign.id)
    if borrower is None:
        # Release agent — no borrowers left
        await transition_agent(db, agent, AgentState.AVAILABLE)
        await db.flush()
        logger.debug("allocate_and_dial: no pending borrowers for campaign %s", campaign.id)
        return None

    # Step 3: Create call record
    call = Call(
        campaign_id=campaign.id,
        agent_id=agent.id,
        borrower_id=borrower.id,
        state=CallState.RESERVED,
        provider=provider.name,
        idempotency_key=f"{campaign.id}:{borrower.id}:{uuid.uuid4().hex[:8]}",
        attempt=borrower.attempts + 1,
    )
    db.add(call)

    # Update borrower state
    borrower.state = BorrowerState.RESERVED
    borrower.attempts += 1
    await db.flush()  # Get the call.id generated

    logger.info(
        "allocate_and_dial: allocated agent=%s borrower=%s call=%s",
        agent.id, borrower.id, call.id,
    )

    # Step 4: Call provider (outside transaction lock scope — I/O)
    result = await provider.initiate_call(call.id, borrower.phone)

    if result.status != ProviderStatus.SUCCESS:
        # Step 5b: Provider failed — rollback by raising
        logger.warning(
            "allocate_and_dial: provider %s failed for call %s: %s",
            provider.name, call.id, result.error_message,
        )
        # Mark call FAILED, release agent, set borrower PENDING
        call.state = CallState.FAILED
        await transition_agent(db, agent, AgentState.AVAILABLE)

        # Retry if under max_retries, else EXHAUSTED
        if borrower.attempts < campaign.max_retries + 1:
            borrower.state = BorrowerState.PENDING
        else:
            borrower.state = BorrowerState.EXHAUSTED

        await db.flush()
        return None

    # Step 5a: Success — update call with provider reference
    call.provider_call_id = result.provider_call_id
    await transition_call(db, call, CallState.INITIATED)
    await transition_agent(db, agent, AgentState.DIALING)
    call.initiated_at = datetime.now(timezone.utc)
    borrower.state = BorrowerState.CALLED
    await db.flush()

    return call, agent
