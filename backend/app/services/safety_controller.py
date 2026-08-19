"""
Safety Controller — mandatory gate between pacing engine and telecom provider.

The Safety Controller is the ONLY path from a dial request to the provider.
The Pacing Engine CANNOT talk to the provider directly — it must pass through here.

Decision matrix (evaluated top-to-bottom, first match wins):

  Priority 1 — FALLBACK:
    abandoned_rate > 3%
    → Regulators require <3% abandoned rate on outbound campaigns.
    → Force 1:1 progressive (approved = available_agents). No predictive multiplier.

  Priority 2 — REJECT:
    provider_health < 0.40
    → Provider is critically degraded. Placing calls will mostly fail, wasting
      agents and borrowers. Stop dialing until health recovers.
    → approved = 0

  Priority 3 — REDUCE:
    provider_health < 0.70
    OR requested_count > available_agents * MAX_RATIO (3.0)
    → Provider is degraded OR pacing engine is being too aggressive.
    → Cap at available_agents * REDUCE_RATIO (1.5)

  Priority 4 — APPROVE:
    Everything within safe thresholds.
    → Pass requested_count through unchanged.

This structure means:
  - Abandoned rate protection always wins (compliance > throughput)
  - Provider health gates come before throughput concerns
  - Multiplier safety cap comes last
"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Thresholds (all tunable via config in production)
ABANDONED_RATE_LIMIT = 0.03      # 3% — regulatory limit
PROVIDER_CRITICAL_THRESHOLD = 0.40  # Below → REJECT
PROVIDER_DEGRADED_THRESHOLD = 0.70  # Below → REDUCE
MAX_DIAL_RATIO = 3.0             # Max calls / available_agents
REDUCE_DIAL_RATIO = 1.5          # Reduced cap


class SafetyAction(str, Enum):
    APPROVE  = "APPROVE"
    REDUCE   = "REDUCE"
    REJECT   = "REJECT"
    FALLBACK = "FALLBACK"


@dataclass(frozen=True)
class SafetyDecision:
    """Immutable result of a safety controller evaluation."""
    action: SafetyAction
    approved_count: int
    reason: str
    requested_count: int
    available_agents: int
    provider_health: float
    answer_rate: float
    abandoned_rate: float


def evaluate(
    *,
    requested_count: int,
    available_agents: int,
    provider_health: float,
    answer_rate: float,
    abandoned_rate: float,
) -> SafetyDecision:
    """
    Evaluate whether to approve, reduce, reject, or fall back a dial request.

    Args:
        requested_count:  Number of calls the pacing engine wants to place.
        available_agents: Agents currently in AVAILABLE state.
        provider_health:  Current provider health score [0.0, 1.0].
        answer_rate:      Observed answer rate [0.0, 1.0].
        abandoned_rate:   Fraction of calls abandoned (no agent) [0.0, 1.0].

    Returns:
        SafetyDecision with approved_count and full audit trail.
    """

    # ── Priority 1: FALLBACK (abandoned rate compliance) ──────────────────
    if abandoned_rate > ABANDONED_RATE_LIMIT:
        approved = max(0, available_agents)  # Fall back to strict 1:1
        reason = (
            f"FALLBACK: abandoned_rate={abandoned_rate:.1%} exceeds limit "
            f"{ABANDONED_RATE_LIMIT:.1%} — forced to 1:1 progressive"
        )
        logger.warning("SafetyController: %s", reason)
        return SafetyDecision(
            action=SafetyAction.FALLBACK,
            approved_count=approved,
            reason=reason,
            requested_count=requested_count,
            available_agents=available_agents,
            provider_health=provider_health,
            answer_rate=answer_rate,
            abandoned_rate=abandoned_rate,
        )

    # ── Priority 2: REJECT (provider critically degraded) ─────────────────
    if provider_health < PROVIDER_CRITICAL_THRESHOLD:
        reason = (
            f"REJECT: provider_health={provider_health:.2f} below critical "
            f"threshold {PROVIDER_CRITICAL_THRESHOLD} — no calls placed"
        )
        logger.warning("SafetyController: %s", reason)
        return SafetyDecision(
            action=SafetyAction.REJECT,
            approved_count=0,
            reason=reason,
            requested_count=requested_count,
            available_agents=available_agents,
            provider_health=provider_health,
            answer_rate=answer_rate,
            abandoned_rate=abandoned_rate,
        )

    # ── Priority 3: REDUCE (degraded provider or aggressive pacing) ────────
    over_ratio = available_agents > 0 and (requested_count / available_agents) > MAX_DIAL_RATIO
    if provider_health < PROVIDER_DEGRADED_THRESHOLD or over_ratio:
        approved = max(0, round(available_agents * REDUCE_DIAL_RATIO))
        approved = min(approved, requested_count)  # Never approve more than asked
        reason_parts = []
        if provider_health < PROVIDER_DEGRADED_THRESHOLD:
            reason_parts.append(
                f"provider_health={provider_health:.2f} < {PROVIDER_DEGRADED_THRESHOLD}"
            )
        if over_ratio:
            ratio = requested_count / max(available_agents, 1)
            reason_parts.append(
                f"dial_ratio={ratio:.1f}x exceeds max {MAX_DIAL_RATIO}x"
            )
        reason = f"REDUCE: {'; '.join(reason_parts)} → cap at {REDUCE_DIAL_RATIO}x agents ({approved})"
        logger.info("SafetyController: %s", reason)
        return SafetyDecision(
            action=SafetyAction.REDUCE,
            approved_count=approved,
            reason=reason,
            requested_count=requested_count,
            available_agents=available_agents,
            provider_health=provider_health,
            answer_rate=answer_rate,
            abandoned_rate=abandoned_rate,
        )

    # ── Priority 4: APPROVE ────────────────────────────────────────────────
    reason = (
        f"APPROVE: health={provider_health:.2f} answer_rate={answer_rate:.1%} "
        f"abandoned={abandoned_rate:.1%} all within thresholds"
    )
    logger.info("SafetyController: %s", reason)
    return SafetyDecision(
        action=SafetyAction.APPROVE,
        approved_count=requested_count,
        reason=reason,
        requested_count=requested_count,
        available_agents=available_agents,
        provider_health=provider_health,
        answer_rate=answer_rate,
        abandoned_rate=abandoned_rate,
    )
