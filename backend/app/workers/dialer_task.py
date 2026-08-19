"""
Celery dialer task — wraps the async dialing_cycle for distributed execution.

Why Celery instead of asyncio.create_task()?
  - Multiple worker processes across machines: horizontal scaling
  - Task visibility_timeout: if worker dies, Redis re-queues after 60s
  - task_acks_late + reject_on_worker_lost: no task loss on crash
  - Celery Flower: real-time worker monitoring dashboard
  - Beat scheduler: periodic tasks (heartbeat, cleanup)

Crash recovery flow:
  1. Worker picks up dialer_task, starts dialing
  2. Worker process crashes (OOM, kill signal, etc.)
  3. Redis: task not acked → re-queued after visibility_timeout (60s)
  4. Second worker picks up task → resumes dialing from current DB state
  5. Agent SKIP LOCKED ensures no double-reservation on resume
"""

import asyncio
import logging
import uuid

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    name="smartdialer.dialer_task",
    acks_late=True,
)
def dialer_task(self, campaign_id: str, provider_type: str = "PROVIDER_A") -> dict:
    """
    Celery task: run one dialing cycle for a campaign.

    This task is designed to be called repeatedly by the simulation runner
    or by Celery Beat for periodic execution.

    Returns a summary of the cycle for task result inspection.
    """
    try:
        result = asyncio.run(_run_cycle(campaign_id, provider_type))
        return result
    except Exception as exc:
        logger.error("dialer_task failed for campaign %s: %s", campaign_id, exc)
        raise self.retry(exc=exc, countdown=5)


async def _run_cycle(campaign_id: str, provider_type: str) -> dict:
    """Async implementation of the dialing cycle (called from sync Celery task)."""
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.campaign import Campaign, CampaignState
    from app.providers.registry import get_provider
    from app.services.dialer import dialing_cycle

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        )
        campaign = result.scalar_one_or_none()

        if campaign is None:
            return {"error": f"Campaign {campaign_id} not found"}
        if campaign.state != CampaignState.ACTIVE:
            return {"skipped": True, "reason": f"Campaign state={campaign.state}"}

        provider = get_provider(provider_type)
        summary = await dialing_cycle(db, campaign, provider)

        logger.info(
            "dialer_task: campaign=%s placed=%d decision=%s",
            campaign_id, summary.get("placed", 0), summary.get("decision"),
        )
        return summary
