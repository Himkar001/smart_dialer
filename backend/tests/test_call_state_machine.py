"""
Tests for Call State Machine.

Covers:
- All valid call transitions
- Invalid transitions raise InvalidCallTransitionError
- Duplicate events are idempotent (no double transition)
- Out-of-order events are rejected gracefully
- process_provider_event correctly maps event strings to states
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call, CallState
from app.services.call_state_machine import (
    VALID_CALL_TRANSITIONS,
    InvalidCallTransitionError,
    count_calls_by_state,
    process_provider_event,
    transition_call,
)

pytestmark = pytest.mark.asyncio


class TestValidCallTransitions:
    """All valid call transitions must succeed."""

    async def test_queued_to_reserved(self, db: AsyncSession, queued_call: Call):
        result = await transition_call(db, queued_call, CallState.RESERVED)
        assert result.state == CallState.RESERVED

    async def test_reserved_to_initiated(self, db: AsyncSession, queued_call: Call):
        await transition_call(db, queued_call, CallState.RESERVED)
        result = await transition_call(db, queued_call, CallState.INITIATED)
        assert result.state == CallState.INITIATED
        assert result.initiated_at is not None

    async def test_initiated_to_ringing(self, db: AsyncSession, queued_call: Call):
        await transition_call(db, queued_call, CallState.RESERVED)
        await transition_call(db, queued_call, CallState.INITIATED)
        result = await transition_call(db, queued_call, CallState.RINGING)
        assert result.state == CallState.RINGING

    async def test_ringing_to_answered(self, db: AsyncSession, queued_call: Call):
        await transition_call(db, queued_call, CallState.RESERVED)
        await transition_call(db, queued_call, CallState.INITIATED)
        await transition_call(db, queued_call, CallState.RINGING)
        result = await transition_call(db, queued_call, CallState.ANSWERED)
        assert result.state == CallState.ANSWERED

    async def test_answered_to_connected(self, db: AsyncSession, queued_call: Call):
        await transition_call(db, queued_call, CallState.RESERVED)
        await transition_call(db, queued_call, CallState.INITIATED)
        await transition_call(db, queued_call, CallState.RINGING)
        await transition_call(db, queued_call, CallState.ANSWERED)
        result = await transition_call(db, queued_call, CallState.CONNECTED)
        assert result.state == CallState.CONNECTED
        assert result.connected_at is not None

    async def test_connected_to_completed(self, db: AsyncSession, queued_call: Call):
        await transition_call(db, queued_call, CallState.RESERVED)
        await transition_call(db, queued_call, CallState.INITIATED)
        await transition_call(db, queued_call, CallState.RINGING)
        await transition_call(db, queued_call, CallState.ANSWERED)
        await transition_call(db, queued_call, CallState.CONNECTED)
        result = await transition_call(db, queued_call, CallState.COMPLETED)
        assert result.state == CallState.COMPLETED
        assert result.completed_at is not None

    async def test_failed_to_queued_retry(self, db: AsyncSession, queued_call: Call):
        await transition_call(db, queued_call, CallState.RESERVED)
        await transition_call(db, queued_call, CallState.FAILED)
        result = await transition_call(db, queued_call, CallState.QUEUED)
        assert result.state == CallState.QUEUED

    async def test_reserved_to_failed(self, db: AsyncSession, queued_call: Call):
        await transition_call(db, queued_call, CallState.RESERVED)
        result = await transition_call(db, queued_call, CallState.FAILED)
        assert result.state == CallState.FAILED
        assert result.completed_at is not None

    async def test_reserved_to_cancelled(self, db: AsyncSession, queued_call: Call):
        await transition_call(db, queued_call, CallState.RESERVED)
        result = await transition_call(db, queued_call, CallState.CANCELLED)
        assert result.state == CallState.CANCELLED


class TestInvalidCallTransitions:
    """Invalid transitions must raise InvalidCallTransitionError."""

    async def test_queued_to_connected_invalid(self, db: AsyncSession, queued_call: Call):
        with pytest.raises(InvalidCallTransitionError):
            await transition_call(db, queued_call, CallState.CONNECTED)

    async def test_queued_to_completed_invalid(self, db: AsyncSession, queued_call: Call):
        with pytest.raises(InvalidCallTransitionError):
            await transition_call(db, queued_call, CallState.COMPLETED)

    async def test_ringing_to_connected_invalid(self, db: AsyncSession, queued_call: Call):
        await transition_call(db, queued_call, CallState.RESERVED)
        await transition_call(db, queued_call, CallState.INITIATED)
        await transition_call(db, queued_call, CallState.RINGING)
        with pytest.raises(InvalidCallTransitionError):
            await transition_call(db, queued_call, CallState.CONNECTED)

    async def test_completed_has_no_transitions(self, db: AsyncSession, queued_call: Call):
        """COMPLETED is a terminal state — nothing can come after it."""
        await transition_call(db, queued_call, CallState.RESERVED)
        await transition_call(db, queued_call, CallState.INITIATED)
        await transition_call(db, queued_call, CallState.RINGING)
        await transition_call(db, queued_call, CallState.ANSWERED)
        await transition_call(db, queued_call, CallState.CONNECTED)
        await transition_call(db, queued_call, CallState.COMPLETED)
        with pytest.raises(InvalidCallTransitionError):
            await transition_call(db, queued_call, CallState.QUEUED)


class TestProviderEventProcessing:
    """process_provider_event: idempotency and out-of-order handling."""

    async def test_ringing_event_advances_state(self, db: AsyncSession, queued_call: Call):
        # Manually put call in INITIATED state
        await transition_call(db, queued_call, CallState.RESERVED)
        await transition_call(db, queued_call, CallState.INITIATED)
        await db.commit()

        key = f"{queued_call.id}:RINGING:1"
        call = await process_provider_event(db, queued_call.id, "RINGING", key)
        await db.commit()
        assert call.state == CallState.RINGING

    async def test_duplicate_event_is_idempotent(self, db: AsyncSession, queued_call: Call):
        """Sending the same event twice must not change state twice."""
        await transition_call(db, queued_call, CallState.RESERVED)
        await transition_call(db, queued_call, CallState.INITIATED)
        await db.commit()

        key = f"{queued_call.id}:RINGING:idempotent"

        # First event — should succeed
        call1 = await process_provider_event(db, queued_call.id, "RINGING", key)
        await db.commit()
        assert call1.state == CallState.RINGING

        # Second event — same key, should be ignored
        call2 = await process_provider_event(db, queued_call.id, "RINGING", key)
        await db.commit()
        # State must still be RINGING, not double-advanced
        assert call2.state == CallState.RINGING

    async def test_out_of_order_event_ignored(self, db: AsyncSession, queued_call: Call):
        """
        COMPLETED event arriving when call is QUEUED must be ignored.
        The call must remain in QUEUED state.
        """
        await db.commit()
        # Call is QUEUED — COMPLETED is not a valid target from QUEUED
        key = f"{queued_call.id}:COMPLETED:ooo"
        call = await process_provider_event(db, queued_call.id, "COMPLETED", key)
        await db.commit()
        assert call.state == CallState.QUEUED  # Unchanged

    async def test_unknown_event_type_ignored(self, db: AsyncSession, queued_call: Call):
        """Unknown event types should not crash the system."""
        await db.commit()
        key = f"{queued_call.id}:UNKNOWN:1"
        call = await process_provider_event(db, queued_call.id, "UNKNOWN_EVENT", key)
        assert call.state == CallState.QUEUED

    async def test_answered_answered_answered_completed_sequence(
        self, db: AsyncSession, queued_call: Call
    ):
        """
        Simulate Provider B sending: ANSWERED, ANSWERED, ANSWERED, COMPLETED.
        Only the first ANSWERED should apply; subsequent are duplicates.
        """
        await transition_call(db, queued_call, CallState.RESERVED)
        await transition_call(db, queued_call, CallState.INITIATED)
        await transition_call(db, queued_call, CallState.RINGING)
        await db.commit()

        base_key = f"{queued_call.id}:ANSWERED"

        # First ANSWERED
        call = await process_provider_event(db, queued_call.id, "ANSWERED", f"{base_key}:1")
        await db.commit()
        assert call.state == CallState.ANSWERED

        # Second ANSWERED — duplicate key, should be ignored
        call = await process_provider_event(db, queued_call.id, "ANSWERED", f"{base_key}:1")
        await db.commit()
        assert call.state == CallState.ANSWERED  # Still ANSWERED, not broken

        # Third ANSWERED with new key — out of order from ANSWERED (ANSWERED→ANSWERED not valid)
        call = await process_provider_event(db, queued_call.id, "ANSWERED", f"{base_key}:2")
        await db.commit()
        assert call.state == CallState.ANSWERED  # Still ANSWERED

        # COMPLETED — manually advance to CONNECTED first
        await transition_call(db, queued_call, CallState.CONNECTED)
        await db.commit()
        call = await process_provider_event(
            db, queued_call.id, "COMPLETED", f"{queued_call.id}:COMPLETED:1"
        )
        await db.commit()
        assert call.state == CallState.COMPLETED


class TestCountCallsByState:
    async def test_count_queued(self, db: AsyncSession, campaign, borrower):
        # 3 queued calls
        calls = [
            Call(
                campaign_id=campaign.id,
                borrower_id=borrower.id,
                state=CallState.QUEUED,
                provider="PROVIDER_A",
                idempotency_key=str(uuid.uuid4()),
            )
            for _ in range(3)
        ]
        db.add_all(calls)
        await db.commit()

        count = await count_calls_by_state(db, campaign.id, [CallState.QUEUED])
        assert count == 3

    async def test_count_multiple_states(self, db: AsyncSession, campaign, borrower):
        calls = [
            Call(campaign_id=campaign.id, borrower_id=borrower.id,
                 state=CallState.RINGING, provider="PROVIDER_A",
                 idempotency_key=str(uuid.uuid4())),
            Call(campaign_id=campaign.id, borrower_id=borrower.id,
                 state=CallState.INITIATED, provider="PROVIDER_A",
                 idempotency_key=str(uuid.uuid4())),
            Call(campaign_id=campaign.id, borrower_id=borrower.id,
                 state=CallState.COMPLETED, provider="PROVIDER_A",
                 idempotency_key=str(uuid.uuid4())),
        ]
        db.add_all(calls)
        await db.commit()

        in_flight = await count_calls_by_state(
            db, campaign.id, [CallState.RINGING, CallState.INITIATED]
        )
        assert in_flight == 2
