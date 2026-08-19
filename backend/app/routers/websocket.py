"""WebSocket router — real-time metrics stream."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import AsyncSessionLocal
from app.services.broadcaster import collect_metrics, manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket) -> None:
    """
    Real-time metrics WebSocket endpoint.

    Connect: ws://localhost:8000/ws/metrics
    Receives: MetricsSnapshot JSON every 2 seconds (pushed by broadcast_loop).

    On connect, immediately send the current snapshot so the dashboard
    doesn't wait up to 2 seconds for the first data.
    """
    await manager.connect(ws)
    try:
        # Send immediate snapshot on connect
        async with AsyncSessionLocal() as db:
            metrics = await collect_metrics(db)
        await ws.send_json(metrics)

        # Keep connection alive — broadcaster handles subsequent pushes
        async for _ in ws.iter_text():
            pass  # Ignore any client messages (ping/pong handled by FastAPI)

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        manager.disconnect(ws)
