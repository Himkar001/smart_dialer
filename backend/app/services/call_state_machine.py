"""
Call State Machine

Key design decisions:
1. process_provider_event() is fully idempotent. Before applying any transition
   it checks a unique DB constraint on call_events.idempotency_key. If the key
   already exists, the event is silently ignored and the current state is returned.

2. Before applying a transition, valid_from_states is checked. Out-of-order
   events (e.g. COMPLETED arriving before RINGING) are rejected gracefully —
   logged as warnings, not errors — and the call remains in its current valid state.

3. Every state change is journaled in call_events for audit trail.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call, CallState
from app.models.call_event import CallEvent

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Valid state transitions
# ------------------------------------------------------------------
VALID_CALL_TRANSITIONS: dict[CallState, list[CallState]] = {
    CallState.QUEUED:     [CallState.RESERVED],
    CallState.RESERVED:   [CallState.INITIATED, CallState.FAILED, CallState.CANCELLED],
    CallState.INITIATED:  [CallState.RINGING, CallState.FAILED, CallState.CANCELLED],
    CallState.RINGING:    [CallState.ANSWERED, CallState.FAILED, CallState.CANCELLED],
    CallState.ANSWERED:   [CallState.CONNECTED, CallState.FAILED],
    CallState.CONNECTED:  [CallState.COMPLETED, CallState.FAILED],
    CallState.FAILED:     [CallState.QUEUED],     # retry path
    CallState.COMPLETED:  [],                      # terminal
    CallState.CANCELLED:  [],                      # terminal
}

# Map provider event strings → target CallState
EVENT_TO_STATE: dict[str, CallState] = {
    "RINGING":   CallState.RINGING,
    "ANSWERED":  CallState.ANSWERED,
    "CONNECTED": CallState.CONNECTED,
    "COMPLETED": CallState.COMPLETED,
    "FAILED":    CallState.FAILED,
    "CANCELLED": CallState.CANCELLED,
}


class InvalidCallTransitionError(Exception):
    """Raised when an illegal call state transition is attempted."""
    pass


async def transition_call(
    db: AsyncSession,
    call: Call,
    to_state: CallState,
) -> Call:
    """
    Transition a call to a new state with guard check.

    Raises:
        InvalidCallTransitionError: If the transition is not in the allow-list.
    """
    allowed = VALID_CALL_TRANSITIONS.get(call.state, [])
    if to_state not in allowed:
        raise InvalidCallTransitionError(
            f"Call {call.id}: transition {call.state} → {to_state} is not allowed. "
            f"Valid targets: {[s.value for s in allowed]}"
        )

    old_state = call.state
    now = datetime.now(timezone.utc)
    call.state = to_state
    call.updated_at = now

    # Timestamp important milestones
    if to_state == CallState.INITIATED:
        call.initiated_at = now
    elif to_state == CallState.CONNECTED:
        call.connected_at = now
    elif to_state in (CallState.COMPLETED, CallState.FAILED, CallState.CANCELLED):
        call.completed_at = now

    await db.flush()
    logger.info("transition_call: call %s  %s → %s", call.id, old_state.value, to_state.value)
    return call


async def process_provider_event(
    db: AsyncSession,
    call_id: uuid.UUID,
    event_type: str,
    idempotency_key: str,
    raw_payload: dict | None = None,
) -> Call:
    """
    Process a provider event idempotently.

    Flow:
    1. Load call (with row lock for concurrent safety).
    2. Look up target state from event_type.
    3. Check if this idempotency_key was already processed — if yes, return current state.
    4. Check if the transition is valid from current state (out-of-order guard).
    5. Apply transition and write audit event atomically.

    Returns:
        The (possibly updated) call.
    """
    from sqlalchemy import select

    # Load call — use row lock on PostgreSQL, plain select on SQLite
    try:
        dialect = db.get_bind().dialect.name  # type: ignore[attr-defined]
    except Exception:
        dialect = "sqlite"

    load_query = select(Call).where(Call.id == call_id)
    if dialect == "postgresql":
        load_query = load_query.with_for_update()
    result = await db.execute(load_query)
    call = result.scalar_one_or_none()
    if call is None:
        raise ValueError(f"Call {call_id} not found")

    # Map event → target state
    target_state = EVENT_TO_STATE.get(event_type.upper())
    if target_state is None:
        logger.warning("process_provider_event: unknown event type %r for call %s", event_type, call_id)
        return call

    # Guard: out-of-order event check
    allowed = VALID_CALL_TRANSITIONS.get(call.state, [])
    if target_state not in allowed:
        logger.warning(
            "process_provider_event: OUT-OF-ORDER event '%s' for call %s "
            "(current=%s, target=%s) — ignored",
            event_type, call_id, call.state.value, target_state.value,
        )
        return call

    # Idempotency: try to insert the event record inside a savepoint.
    # If the idempotency_key already exists → IntegrityError → duplicate detected.
    event = CallEvent(
        call_id=call_id,
        event_type=event_type.upper(),
        idempotency_key=idempotency_key,
        raw_payload=raw_payload or {},
    )
    try:
        async with db.begin_nested():  # savepoint — rolls back only this nested tx on error
            db.add(event)
            await db.flush()
    except IntegrityError:
        # Duplicate idempotency key — event already processed, state unchanged
        logger.info(
            "process_provider_event: DUPLICATE event '%s' for call %s (key=%s) — ignored",
            event_type, call_id, idempotency_key,
        )
        # Reload call to get fresh state after savepoint rollback
        result = await db.execute(select(Call).where(Call.id == call_id))
        return result.scalar_one()

    # Apply the state transition
    await transition_call(db, call, target_state)
    return call


async def get_call(db: AsyncSession, call_id: uuid.UUID) -> Call | None:
    """Fetch a single call by ID, including its events."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Call).where(Call.id == call_id).options(selectinload(Call.events))
    )
    return result.scalar_one_or_none()


async def count_calls_by_state(
    db: AsyncSession, campaign_id: uuid.UUID, states: list[CallState]
) -> int:
    """Return the count of calls in given states for a campaign."""
    result = await db.execute(
        select(func.count(Call.id))
        .where(Call.campaign_id == campaign_id)
        .where(Call.state.in_(states))
    )
    return result.scalar_one() or 0
