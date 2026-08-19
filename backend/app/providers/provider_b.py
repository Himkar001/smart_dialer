"""
Provider B — Slow & Chaotic Mock

Characteristics:
- Call setup latency: 500ms–3s
- Event spacing: 500ms–3s
- Answer rate: ~60%
- Failure rate: ~15%
- Health score: 0.3–0.8 (fluctuating, degrades under load)
- 30% chance of DUPLICATE events (same event sent twice)
- 20% chance of OUT-OF-ORDER events (COMPLETED before CONNECTED, etc.)

This provider is specifically designed to stress-test the idempotency
and out-of-order handling of the call state machine.
"""

import asyncio
import logging
import random
import uuid

from app.providers.base import ProviderCallResult, ProviderStatus, TelecomProvider

logger = logging.getLogger(__name__)

_ANSWER_RATE = 0.60
_FAILURE_RATE = 0.15
_DUPLICATE_RATE = 0.30
_OOO_RATE = 0.20


class ProviderB(TelecomProvider):
    """Slow, chaotic mock provider. Tests idempotency and out-of-order handling."""

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._health_score = 0.75
        self._consecutive_failures = 0

    @property
    def name(self) -> str:
        return "PROVIDER_B"

    async def initiate_call(
        self, call_id: uuid.UUID, to_number: str
    ) -> ProviderCallResult:
        """Simulate slow call setup with high failure rate."""
        await asyncio.sleep(self._rng.uniform(0.5, 3.0))

        # 15% immediate failure
        if self._rng.random() < _FAILURE_RATE:
            self._consecutive_failures += 1
            self._degrade_health()
            return ProviderCallResult(
                status=ProviderStatus.FAILED,
                provider_call_id=None,
                error_message="Provider B: network error",
            )

        # 5% timeout (returned as TIMEOUT)
        if self._rng.random() < 0.05:
            self._consecutive_failures += 1
            self._degrade_health()
            return ProviderCallResult(
                status=ProviderStatus.TIMEOUT,
                provider_call_id=None,
                error_message="Provider B: gateway timeout",
            )

        self._consecutive_failures = 0
        self._recover_health()
        provider_call_id = f"PRB-{uuid.uuid4().hex[:12].upper()}"
        return ProviderCallResult(
            status=ProviderStatus.SUCCESS,
            provider_call_id=provider_call_id,
        )

    async def get_health_score(self) -> float:
        """Return fluctuating health score that degrades under failures."""
        await asyncio.sleep(0.01)
        jitter = self._rng.uniform(-0.05, 0.05)
        score = max(0.1, min(1.0, self._health_score + jitter))
        return round(score, 3)

    def _degrade_health(self) -> None:
        """Degrade health exponentially with each consecutive failure."""
        self._health_score = max(0.1, self._health_score * 0.85)
        logger.debug("[ProviderB] Health degraded → %.2f", self._health_score)

    def _recover_health(self) -> None:
        """Slowly recover health on successful calls."""
        self._health_score = min(0.80, self._health_score + 0.03)

    def simulate_outage(self) -> None:
        """Force provider into outage state (for Sprint 4 failure scenarios)."""
        self._health_score = 0.1
        self._consecutive_failures = 10
        logger.warning("[ProviderB] OUTAGE SIMULATED — health=0.1")

    def restore(self) -> None:
        """Restore provider to normal health."""
        self._health_score = 0.70
        self._consecutive_failures = 0
        logger.info("[ProviderB] RESTORED — health=0.70")

    async def simulate_call_events(
        self, call_id: uuid.UUID, answer_rate_override: float | None = None
    ):
        """
        Yield chaotic events: may include duplicates and out-of-order events.

        The call state machine MUST handle all of these gracefully.
        """
        answer_rate = answer_rate_override if answer_rate_override is not None else _ANSWER_RATE
        send_duplicate = self._rng.random() < _DUPLICATE_RATE
        send_ooo = self._rng.random() < _OOO_RATE

        # --- RINGING ---
        await asyncio.sleep(self._rng.uniform(0.5, 2.0))
        yield ("RINGING", f"{call_id}:RINGING:1")

        # Duplicate RINGING — state machine must ignore this
        if send_duplicate:
            await asyncio.sleep(0.1)
            logger.debug("[ProviderB] Sending DUPLICATE RINGING for %s", call_id)
            yield ("RINGING", f"{call_id}:RINGING:1")  # Same idempotency key

        answered = self._rng.random() < answer_rate

        if answered:
            await asyncio.sleep(self._rng.uniform(0.5, 2.0))
            yield ("ANSWERED", f"{call_id}:ANSWERED:1")

            # Out-of-order: send COMPLETED before CONNECTED
            if send_ooo:
                await asyncio.sleep(0.1)
                logger.debug("[ProviderB] Sending OUT-OF-ORDER COMPLETED for %s", call_id)
                yield ("COMPLETED", f"{call_id}:COMPLETED:ooo")  # Must be rejected by SM

            await asyncio.sleep(self._rng.uniform(0.3, 1.0))
            yield ("CONNECTED", f"{call_id}:CONNECTED:1")

            # Duplicate CONNECTED
            if send_duplicate:
                await asyncio.sleep(0.1)
                yield ("CONNECTED", f"{call_id}:CONNECTED:1")  # Same key — ignored

            await asyncio.sleep(self._rng.uniform(2.0, 6.0))
            yield ("COMPLETED", f"{call_id}:COMPLETED:1")
        else:
            await asyncio.sleep(self._rng.uniform(1.0, 3.0))
            yield ("FAILED", f"{call_id}:FAILED:1")
