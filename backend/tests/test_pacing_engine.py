"""
Tests for Predictive Pacing Engine + Answer Rate Tracker.
"""

import math
import uuid

import pytest

from app.services.answer_rate_tracker import AnswerRateTracker, COLD_START_THRESHOLD
from app.services.pacing_engine import (
    TARGET_UTILISATION,
    MIN_ANSWER_RATE,
    calculate_predictive_count,
    compute_pacing_decision,
)
from app.services.safety_controller import SafetyAction

pytestmark = pytest.mark.asyncio


class TestAnswerRateTracker:
    def test_cold_start_returns_none(self):
        t = AnswerRateTracker(window=100)
        assert t.get_answer_rate("campaign-1") is None

    def test_returns_none_below_threshold(self):
        t = AnswerRateTracker(window=100)
        for _ in range(COLD_START_THRESHOLD - 1):
            t.record("c1", True)
        assert t.get_answer_rate("c1") is None

    def test_returns_rate_at_threshold(self):
        t = AnswerRateTracker(window=100)
        for _ in range(COLD_START_THRESHOLD):
            t.record("c1", True)
        rate = t.get_answer_rate("c1")
        assert rate == 1.0

    def test_correct_rate_calculation(self):
        t = AnswerRateTracker(window=100)
        # 8 answered, 2 failed → 80%
        for _ in range(8):
            t.record("c1", True)
        for _ in range(2):
            t.record("c1", False)
        rate = t.get_answer_rate("c1")
        assert rate == 0.8

    def test_rolling_window_evicts_old(self):
        t = AnswerRateTracker(window=10)
        # Fill with 10 failures
        for _ in range(10):
            t.record("c1", False)
        # Now push 10 successes — old failures evicted
        for _ in range(10):
            t.record("c1", True)
        assert t.get_answer_rate("c1") == 1.0

    def test_is_cold_start(self):
        t = AnswerRateTracker()
        assert t.is_cold_start("new-campaign")

    def test_reset_clears_history(self):
        t = AnswerRateTracker()
        for _ in range(20):
            t.record("c1", True)
        t.reset("c1")
        assert t.is_cold_start("c1")

    def test_sample_size(self):
        t = AnswerRateTracker()
        for _ in range(15):
            t.record("c1", True)
        assert t.get_sample_size("c1") == 15

    def test_multiple_campaigns_independent(self):
        t = AnswerRateTracker()
        for _ in range(15):
            t.record("campaign-a", True)
        for _ in range(15):
            t.record("campaign-b", False)
        assert t.get_answer_rate("campaign-a") == 1.0
        assert t.get_answer_rate("campaign-b") == 0.0


class TestCalculatePredictiveCount:
    def test_formula_80pct_answer_rate(self):
        """agents=10, rate=0.80 → ceil(8.5/0.80) = 11"""
        count = calculate_predictive_count(10, 0.80)
        expected = math.ceil(10 * TARGET_UTILISATION / 0.80)
        assert count == expected

    def test_formula_50pct_answer_rate(self):
        """agents=10, rate=0.50 → ceil(8.5/0.50) = 17"""
        count = calculate_predictive_count(10, 0.50)
        expected = math.ceil(10 * TARGET_UTILISATION / 0.50)
        assert count == expected

    def test_zero_agents_returns_zero(self):
        assert calculate_predictive_count(0, 0.80) == 0

    def test_min_answer_rate_floor(self):
        """Very low answer rate is floored at MIN_ANSWER_RATE."""
        count_low = calculate_predictive_count(10, 0.01)  # Below floor
        count_floor = calculate_predictive_count(10, MIN_ANSWER_RATE)
        assert count_low == count_floor

    def test_higher_agents_more_calls(self):
        assert calculate_predictive_count(20, 0.70) > calculate_predictive_count(10, 0.70)

    def test_lower_answer_rate_more_calls(self):
        assert calculate_predictive_count(10, 0.40) > calculate_predictive_count(10, 0.80)

    def test_100pct_answer_rate(self):
        """At 100% answer rate, dial slightly fewer than agents * utilisation."""
        count = calculate_predictive_count(10, 1.0)
        assert count == math.ceil(10 * TARGET_UTILISATION / 1.0)


class TestComputePacingDecision:
    async def test_progressive_mode_requests_available(self):
        """Progressive mode always requests exactly available_agents."""
        t = AnswerRateTracker()
        decision = await compute_pacing_decision(
            campaign_id=uuid.uuid4(),
            available_agents=10,
            in_flight_calls=0,
            provider_health=0.95,
            abandoned_rate=0.0,
            mode="PROGRESSIVE",
            answer_rate_tracker=t,
        )
        assert decision.requested_count == 10

    async def test_cold_start_falls_back_to_progressive(self):
        """With no history, predictive falls back to 1:1."""
        t = AnswerRateTracker()
        decision = await compute_pacing_decision(
            campaign_id=uuid.uuid4(),
            available_agents=10,
            in_flight_calls=0,
            provider_health=0.95,
            abandoned_rate=0.0,
            mode="PREDICTIVE",
            answer_rate_tracker=t,  # Empty — cold start
        )
        assert decision.requested_count == 10  # Progressive fallback

    async def test_predictive_requests_more_than_agents(self):
        """With warm data and good health, predictive requests >available."""
        t = AnswerRateTracker()
        cid = str(uuid.uuid4())
        # Warm up with 70% answer rate
        for _ in range(7):
            t.record(cid, True)
        for _ in range(3):
            t.record(cid, False)

        decision = await compute_pacing_decision(
            campaign_id=uuid.UUID(cid),
            available_agents=10,
            in_flight_calls=0,
            provider_health=0.95,
            abandoned_rate=0.0,
            mode="PREDICTIVE",
            answer_rate_tracker=t,
        )
        assert decision.requested_count > 10

    async def test_safety_controller_always_called(self):
        """Even with good params, safety controller is always invoked."""
        t = AnswerRateTracker()
        decision = await compute_pacing_decision(
            campaign_id=uuid.uuid4(),
            available_agents=0,  # No agents
            in_flight_calls=0,
            provider_health=0.95,
            abandoned_rate=0.0,
            mode="PROGRESSIVE",
            answer_rate_tracker=t,
        )
        # approved_count always comes from safety controller
        assert decision.approved_count == 0

    async def test_rejected_when_provider_critical(self):
        """Low provider health triggers REJECT via safety controller."""
        t = AnswerRateTracker()
        decision = await compute_pacing_decision(
            campaign_id=uuid.uuid4(),
            available_agents=20,
            in_flight_calls=0,
            provider_health=0.10,  # Critical
            abandoned_rate=0.0,
            mode="PROGRESSIVE",
            answer_rate_tracker=t,
        )
        assert decision.action == SafetyAction.REJECT
        assert decision.approved_count == 0
