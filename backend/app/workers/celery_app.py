"""
Celery application — distributed task queue for the dialer worker.

Uses Redis as both broker and result backend.
In development: `celery -A app.workers.celery_app worker --loglevel=info`
In Docker: the `worker` service runs this automatically.
"""

from celery import Celery
from app.config import settings

celery_app = Celery(
    "smartdialer",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.dialer_task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Retry tasks up to 3 times on unexpected failure
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Heartbeat so we can detect crashed workers
    worker_heartbeat_interval=10,
    broker_heartbeat=10,
    # Visibility timeout: if a worker crashes mid-task, re-queue after 60s
    broker_transport_options={"visibility_timeout": 60},
)
