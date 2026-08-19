"""
WebSocket Connection Manager + Metrics Broadcaster.

Broadcasts a real-time MetricsSnapshot to all connected dashboard clients
every 2 seconds. Uses asyncio.gather to send to all connections concurrently.
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import WebSocket
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentState
from app.models.call import Call, CallState

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages all active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("WebSocket connected (total=%d)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard if hasattr(self._connections, "discard") else None
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info("WebSocket disconnected (total=%d)", len(self._connections))

    async def broadcast(self, data: dict) -> None:
        """Send JSON to all connected clients; remove dead connections."""
        dead = []
        for ws in list(self._connections):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


# Global singleton used by the WebSocket router and the background broadcaster
manager = ConnectionManager()


async def collect_metrics(db: AsyncSession) -> dict:
    """Query current state counts and return a MetricsSnapshot dict."""

    # Agent counts by state
    agent_rows = await db.execute(
        select(Agent.state, func.count(Agent.id))
        .group_by(Agent.state)
    )
    agent_counts: dict[str, int] = {row[0].value: row[1] for row in agent_rows}

    # Call counts by state
    call_rows = await db.execute(
        select(Call.state, func.count(Call.id))
        .group_by(Call.state)
    )
    call_counts: dict[str, int] = {row[0].value: row[1] for row in call_rows}

    # Provider health scores
    from app.providers.registry import get_all_providers
    providers = get_all_providers()
    provider_health: dict[str, float] = {}
    for name, p in providers.items():
        try:
            provider_health[name] = await p.get_health_score()
        except Exception:
            provider_health[name] = 0.0

    total_completed = call_counts.get("COMPLETED", 0)
    total_failed = call_counts.get("FAILED", 0)
    total_finished = total_completed + total_failed
    abandoned_rate = round(total_failed / total_finished, 4) if total_finished > 0 else 0.0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agents": {
            "total": sum(agent_counts.values()),
            "offline": agent_counts.get("OFFLINE", 0),
            "available": agent_counts.get("AVAILABLE", 0),
            "reserved": agent_counts.get("RESERVED", 0),
            "dialing": agent_counts.get("DIALING", 0),
            "connected": agent_counts.get("CONNECTED", 0),
            "wrap_up": agent_counts.get("WRAP_UP", 0),
            "paused": agent_counts.get("PAUSED", 0),
        },
        "calls": {
            "queued": call_counts.get("QUEUED", 0),
            "initiated": call_counts.get("INITIATED", 0),
            "ringing": call_counts.get("RINGING", 0),
            "connected": call_counts.get("CONNECTED", 0),
            "completed": total_completed,
            "failed": total_failed,
            "cancelled": call_counts.get("CANCELLED", 0),
        },
        "provider_health": provider_health,
        "safety": {
            "last_decision": None,
            "last_reason": None,
            "abandoned_rate": abandoned_rate,
        },
        "pacing": {
            "mode": "PROGRESSIVE",
            "dial_count_requested": 0,
            "dial_count_approved": 0,
            "answer_rate": 0.0,
            "provider_health": provider_health.get("PROVIDER_A", 0.0),
        },
    }


async def broadcast_loop(get_db_session) -> None:
    """
    Background task: collect metrics and broadcast every 2 seconds.
    Started on FastAPI startup, runs until shutdown.
    """
    logger.info("Metrics broadcast loop starting")
    while True:
        try:
            if manager.count > 0:
                async with get_db_session() as db:
                    metrics = await collect_metrics(db)
                await manager.broadcast(metrics)
        except Exception as e:
            logger.error("broadcast_loop error: %s", e)
        await asyncio.sleep(2)
