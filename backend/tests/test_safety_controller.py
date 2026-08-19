"""
Tests for Safety Controller — all 4 decision paths.

Architecture test: verifies the Safety Controller cannot be bypassed.
"""

import pytest

from app.services.safety_controller import (
    ABANDONED_RATE_LIMIT,
    PROVIDER_CRITICAL_THRESHOLD,
    PROVIDER_DEGRADED_THRESHOLD,
    REDUCE_DIAL_RATIO,
    SafetyAction,
    evaluate,
)


class TestFallbackPath:
    """Priority 1: abandoned_rate > 3% → FALLBACK."""

    def test_fallback_triggered_at_limit(self):
        d = evaluate(
            requested_count=30,
            available_agents=10,
            provider_health=0.95,
            answer_rate=0.80,
            abandoned_rate=0.031,  # just over 3%
        )
        assert d.action == SafetyAction.FALLBACK

    def test_fallback_approved_equals_available_agents(self):
        d = evaluate(
            requested_count=50,
            available_agents=10,
            provider_health=0.90,
            answer_rate=0.70,
            abandoned_rate=0.05,
        )
        assert d.action == SafetyAction.FALLBACK
        assert d.approved_count == 10  # strict 1:1

    def test_fallback_wins_over_reject(self):
        """FALLBACK (Priority 1) beats REJECT (Priority 2)."""
        d = evaluate(
            requested_count=20,
            available_agents=5,
            provider_health=0.10,  # Would trigger REJECT
            answer_rate=0.50,
            abandoned_rate=0.05,   # Triggers FALLBACK first
        )
        assert d.action == SafetyAction.FALLBACK

    def test_no_fallback_at_exact_limit(self):
        """Exactly 3% should NOT trigger FALLBACK (strictly greater than)."""
        d = evaluate(
            requested_count=10,
            available_agents=10,
            provider_health=0.90,
            answer_rate=0.80,
            abandoned_rate=ABANDONED_RATE_LIMIT,  # exactly 3% — not triggered
        )
        assert d.action == SafetyAction.APPROVE


class TestRejectPath:
    """Priority 2: provider_health < 0.40 → REJECT."""

    def test_reject_below_critical(self):
        d = evaluate(
            requested_count=20,
            available_agents=10,
            provider_health=0.35,
            answer_rate=0.60,
            abandoned_rate=0.01,
        )
        assert d.action == SafetyAction.REJECT
        assert d.approved_count == 0

    def test_reject_at_exactly_critical(self):
        """health == 0.40 should NOT reject (strictly less than)."""
        d = evaluate(
            requested_count=10,
            available_agents=10,
            provider_health=PROVIDER_CRITICAL_THRESHOLD,
            answer_rate=0.60,
            abandoned_rate=0.01,
        )
        assert d.action != SafetyAction.REJECT

    def test_reject_zero_approved(self):
        d = evaluate(
            requested_count=100,
            available_agents=50,
            provider_health=0.10,
            answer_rate=0.50,
            abandoned_rate=0.00,
        )
        assert d.approved_count == 0

    def test_reject_reason_mentions_health(self):
        d = evaluate(
            requested_count=10,
            available_agents=10,
            provider_health=0.20,
            answer_rate=0.50,
            abandoned_rate=0.00,
        )
        assert "0.20" in d.reason or "health" in d.reason.lower()


class TestReducePath:
    """Priority 3: degraded health OR over ratio → REDUCE."""

    def test_reduce_on_degraded_health(self):
        d = evaluate(
            requested_count=10,
            available_agents=10,
            provider_health=0.55,  # Between 0.40 and 0.70
            answer_rate=0.70,
            abandoned_rate=0.01,
        )
        assert d.action == SafetyAction.REDUCE
        assert d.approved_count <= d.requested_count

    def test_reduce_caps_at_ratio(self):
        """Reduced count = round(available * 1.5)."""
        available = 10
        d = evaluate(
            requested_count=50,
            available_agents=available,
            provider_health=0.55,
            answer_rate=0.70,
            abandoned_rate=0.00,
        )
        assert d.action == SafetyAction.REDUCE
        assert d.approved_count == round(available * REDUCE_DIAL_RATIO)

    def test_reduce_on_over_ratio(self):
        """requested > available * 3.0 triggers REDUCE even with good health."""
        d = evaluate(
            requested_count=40,  # 40 > 10 * 3.0 = 30
            available_agents=10,
            provider_health=0.85,  # Healthy
            answer_rate=0.30,      # Low answer rate → predictive requests many
            abandoned_rate=0.01,
        )
        assert d.action == SafetyAction.REDUCE

    def test_reduce_never_exceeds_requested(self):
        """If available * 1.5 > requested, return min(both)."""
        d = evaluate(
            requested_count=5,
            available_agents=10,
            provider_health=0.55,
            answer_rate=0.70,
            abandoned_rate=0.00,
        )
        assert d.approved_count <= 5


class TestApprovePath:
    """Priority 4: all thresholds met → APPROVE."""

    def test_approve_healthy_conditions(self):
        d = evaluate(
            requested_count=12,
            available_agents=10,
            provider_health=0.95,
            answer_rate=0.80,
            abandoned_rate=0.01,
        )
        assert d.action == SafetyAction.APPROVE
        assert d.approved_count == 12

    def test_approve_passes_through_exact_count(self):
        d = evaluate(
            requested_count=17,
            available_agents=10,
            provider_health=0.92,
            answer_rate=0.75,
            abandoned_rate=0.00,
        )
        assert d.action == SafetyAction.APPROVE
        assert d.approved_count == 17

    def test_approve_zero_requested(self):
        d = evaluate(
            requested_count=0,
            available_agents=0,
            provider_health=0.95,
            answer_rate=0.80,
            abandoned_rate=0.00,
        )
        assert d.action == SafetyAction.APPROVE
        assert d.approved_count == 0


class TestArchitectureIsolation:
    """Verify Safety Controller cannot return more than was requested (no amplification)."""

    def test_approve_never_amplifies(self):
        for requested in [1, 5, 10, 50, 100]:
            d = evaluate(
                requested_count=requested,
                available_agents=20,
                provider_health=0.95,
                answer_rate=0.80,
                abandoned_rate=0.00,
            )
            assert d.approved_count <= requested, (
                f"Safety Controller amplified: requested={requested} approved={d.approved_count}"
            )

    def test_decision_always_has_reason(self):
        for health in [0.1, 0.5, 0.75, 0.95]:
            d = evaluate(
                requested_count=10,
                available_agents=10,
                provider_health=health,
                answer_rate=0.70,
                abandoned_rate=0.00,
            )
            assert d.reason, "Every decision must have a reason for audit trail"

    def test_frozen_dataclass_immutable(self):
        d = evaluate(
            requested_count=10,
            available_agents=10,
            provider_health=0.95,
            answer_rate=0.80,
            abandoned_rate=0.00,
        )
        with pytest.raises(Exception):  # frozen dataclass raises
            d.approved_count = 999  # type: ignore
