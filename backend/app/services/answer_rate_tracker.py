"""
Answer Rate Tracker — rolling window for call outcome statistics.

Uses a collections.deque as in-memory storage. Interface is designed
to be identical to a Redis SORTED SET implementation, making it trivial
to swap to Redis in production without changing callers.

Tracks last N call outcomes per campaign. An "outcome" is either:
  - ANSWERED (True)  — call reached CONNECTED state
  - NO_ANSWER (False) — call ended in FAILED/CANCELLED without connecting
"""

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Deque

logger = logging.getLogger(__name__)

# Default rolling window size
DEFAULT_WINDOW = 100

# Cold-start threshold: minimum outcomes needed before making predictions
COLD_START_THRESHOLD = 10


class CallOutcome:
    __slots__ = ("answered", "timestamp")

    def __init__(self, answered: bool) -> None:
        self.answered = answered
        self.timestamp = datetime.now(timezone.utc)


class AnswerRateTracker:
    """
    Per-campaign rolling answer rate tracker.

    In production this would persist to Redis with TTL-based expiry.
    Here we use an in-memory deque — same O(1) push, O(n) scan interface.
    """

    def __init__(self, window: int = DEFAULT_WINDOW) -> None:
        self._window = window
        # campaign_id → deque of outcomes
        self._data: dict[str, Deque[CallOutcome]] = {}

    def record(self, campaign_id: str, answered: bool) -> None:
        """Record a call outcome (thread-safe for asyncio — single event loop)."""
        if campaign_id not in self._data:
            self._data[campaign_id] = deque(maxlen=self._window)
        self._data[campaign_id].append(CallOutcome(answered))
        logger.debug(
            "AnswerRateTracker: campaign=%s answered=%s window_size=%d",
            campaign_id, answered, len(self._data[campaign_id]),
        )

    def get_answer_rate(self, campaign_id: str) -> float | None:
        """
        Return answer rate [0.0, 1.0] for the last `window` calls.

        Returns None if fewer than COLD_START_THRESHOLD outcomes exist
        (cold start — caller should fall back to progressive mode).
        """
        outcomes = self._data.get(campaign_id)
        if not outcomes or len(outcomes) < COLD_START_THRESHOLD:
            return None  # Cold start

        answered = sum(1 for o in outcomes if o.answered)
        rate = answered / len(outcomes)
        return round(rate, 4)

    def get_sample_size(self, campaign_id: str) -> int:
        """Return current sample count for a campaign."""
        outcomes = self._data.get(campaign_id)
        return len(outcomes) if outcomes else 0

    def is_cold_start(self, campaign_id: str) -> bool:
        """True if not enough data for predictive pacing yet."""
        return self.get_sample_size(campaign_id) < COLD_START_THRESHOLD

    def reset(self, campaign_id: str) -> None:
        """Clear history for a campaign (e.g. when mode changes)."""
        self._data.pop(campaign_id, None)


# Process-level singleton — shared across all simulation runs
tracker = AnswerRateTracker(window=DEFAULT_WINDOW)
