"""
Predictive Pacing Engine.

Algorithm:
  1. Check cold start → if insufficient history, fall back to progressive
  2. Fetch: available_agents, answer_rate, in_flight_calls, provider_health
  3. Calculate raw predictive count using the utilisation formula
  4. Pass through Safety Controller (mandatory gate — no bypass possible)
  5. Return SafetyDecision with approved_count

Predictive Formula:
  The key insight: if we expect only P% of calls to be answered (connected),
  we can dial MORE calls simultaneously — knowing that (1-P)% will fail fast.

  target_connected = available_agents * TARGET_UTILISATION   (0.85 default)
  raw_count        = ceil(target_connected / max(answer_rate, MIN_ANSWER_RATE))

  Where MIN_ANSWER_RATE = 0.10 prevents division by tiny numbers from
  causing an explosive dial count.

  Examples:
    agents=10, answer_rate=0.80 → raw = ceil(8.5 / 0.80) = 11
    agents=10, answer_rate=0.50 → raw = ceil(8.5 / 0.50) = 17
    agents=10, answer_rate=0.20 → raw = ceil(8.5 / 0.20) = 43 → CAPPED by Safety

  The Safety Controller is the backstop — raw_count is just a request.
"""

import logging
import math
import uuid

from app.services.answer_rate_tracker import AnswerRateTracker, tracker as global_tracker
from app.services import safety_controller
from app.services.safety_controller import SafetyDecision

logger = logging.getLogger(__name__)

TARGET_UTILISATION = 0.85   # Aim for 85% agent utilisation
MIN_ANSWER_RATE    = 0.10   # Floor to prevent exploding dial counts
COLD_START_FALLBACK_RATIO = 1.0  # 1:1 until warm


def calculate_predictive_count(
    available_agents: int,
    answer_rate: float,
) -> int:
    """
    Pure function — calculate how many calls to request from Safety Controller.

    Args:
        available_agents: Number of AVAILABLE agents.
        answer_rate:      Observed answer rate (0.0–1.0).

    Returns:
        Requested call count (before safety gate).
    """
    if available_agents <= 0:
        return 0

    effective_rate = max(answer_rate, MIN_ANSWER_RATE)
    target_connected = available_agents * TARGET_UTILISATION
    raw = math.ceil(target_connected / effective_rate)

    logger.debug(
        "pacing_engine: available=%d rate=%.2f target_connected=%.1f raw=%d",
        available_agents, answer_rate, target_connected, raw,
    )
    return raw


async def compute_pacing_decision(
    campaign_id: uuid.UUID,
    available_agents: int,
    in_flight_calls: int,
    provider_health: float,
    abandoned_rate: float,
    mode: str = "PREDICTIVE",
    answer_rate_tracker: AnswerRateTracker | None = None,
) -> SafetyDecision:
    """
    Full pacing pipeline: calculate → safety gate → return decision.

    Progressive mode:   requested = available_agents (strict 1:1)
    Predictive mode:    use answer rate formula, then safety gate
    Cold start:         fall back to progressive until enough history

    The Safety Controller call is unconditional — even progressive mode
    passes through it (ensuring compliance checks always fire).
    """
    tracker = answer_rate_tracker or global_tracker
    campaign_key = str(campaign_id)

    # Get current answer rate (may be None if cold start)
    answer_rate = tracker.get_answer_rate(campaign_key)
    sample_size = tracker.get_sample_size(campaign_key)

    if mode == "PROGRESSIVE" or answer_rate is None:
        # Progressive or cold-start: request exactly available_agents
        requested_count = available_agents
        if mode == "PREDICTIVE" and answer_rate is None:
            logger.info(
                "pacing_engine: COLD START (samples=%d < threshold) — using progressive",
                sample_size,
            )
    else:
        # Predictive: use formula
        requested_count = calculate_predictive_count(available_agents, answer_rate)

    # Mandatory Safety Controller gate
    decision = safety_controller.evaluate(
        requested_count=requested_count,
        available_agents=available_agents,
        provider_health=provider_health,
        answer_rate=answer_rate or 0.0,
        abandoned_rate=abandoned_rate,
    )

    logger.info(
        "pacing_engine: campaign=%s mode=%s samples=%d rate=%s requested=%d → %s approved=%d | %s",
        campaign_id, mode, sample_size,
        f"{answer_rate:.2f}" if answer_rate is not None else "N/A",
        requested_count, decision.action, decision.approved_count, decision.reason,
    )

    return decision
