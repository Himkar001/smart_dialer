"""
Provider A — Fast & Reliable Mock

Characteristics:
- Call setup latency: 50–200ms
- Event spacing: 100–400ms  
- Answer rate: ~80%
- Failure rate: ~2%
- Health score: 0.90–0.98 (stable)
- No duplicates, no out-of-order events
"""

import asyncio
import logging
import random
import uuid

from app.providers.base import ProviderCallResult, ProviderStatus, TelecomProvider

logger = logging.getLogger(__name__)

_ANSWER_RATE = 0.80
_FAILURE_RATE = 0.02


class ProviderA(TelecomProvider):
    """Fast, reliable mock telecom provider."""

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._call_count = 0
        self._failure_count = 0

    @property
    def name(self) -> str:
        return "PROVIDER_A"

    async def initiate_call(
        self, call_id: uuid.UUID, to_number: str
    ) -> ProviderCallResult:
        """Simulate call setup with 50–200ms latency."""
        await asyncio.sleep(self._rng.uniform(0.05, 0.20))
        self._call_count += 1

        # 2% chance of immediate failure at setup
        if self._rng.random() < _FAILURE_RATE:
            self._failure_count += 1
            logger.warning("[ProviderA] Call %s: setup FAILED", call_id)
            return ProviderCallResult(
                status=ProviderStatus.FAILED,
                provider_call_id=None,
                error_message="Call setup rejected by carrier",
            )

        provider_call_id = f"PRA-{uuid.uuid4().hex[:12].upper()}"
        logger.debug("[ProviderA] Call %s initiated → %s", call_id, provider_call_id)
        return ProviderCallResult(
            status=ProviderStatus.SUCCESS,
            provider_call_id=provider_call_id,
        )

    async def get_health_score(self) -> float:
        """Return a stable health score with minor jitter."""
        await asyncio.sleep(0.01)
        base = 0.94
        jitter = self._rng.uniform(-0.04, 0.04)
        return round(max(0.0, min(1.0, base + jitter)), 3)

    async def simulate_call_events(
        self, call_id: uuid.UUID, answer_rate_override: float | None = None
    ):
        """
        Yield ordered events for a successful or failed call.

        Event sequence (happy path):
          RINGING → ANSWERED → CONNECTED → COMPLETED

        On no-answer:
          RINGING → FAILED
        """
        answer_rate = answer_rate_override if answer_rate_override is not None else _ANSWER_RATE

        # RINGING
        await asyncio.sleep(self._rng.uniform(0.1, 0.3))
        yield ("RINGING", f"{call_id}:RINGING:1")

        # Decide: answered or no-answer
        if self._rng.random() < answer_rate:
            await asyncio.sleep(self._rng.uniform(0.1, 0.4))
            yield ("ANSWERED", f"{call_id}:ANSWERED:1")

            await asyncio.sleep(self._rng.uniform(0.05, 0.15))
            yield ("CONNECTED", f"{call_id}:CONNECTED:1")

            # Simulate a short call (1–4 seconds)
            await asyncio.sleep(self._rng.uniform(1.0, 4.0))
            yield ("COMPLETED", f"{call_id}:COMPLETED:1")
        else:
            # No answer
            await asyncio.sleep(self._rng.uniform(0.5, 1.5))
            yield ("FAILED", f"{call_id}:FAILED:1")
