"""FastAPI application factory."""

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import agents, calls, campaigns, health
from app.routers import simulation, websocket

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="SmartDialer API",
        description="Outbound call dialing prototype with Progressive and Predictive modes.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow the React dashboard on port 3000
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router)
    app.include_router(campaigns.router)
    app.include_router(agents.router)
    app.include_router(calls.router)
    app.include_router(simulation.router)
    app.include_router(websocket.router)

    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info("SmartDialer API starting up — env=%s", settings.app_env)
        # Start the WebSocket metrics broadcast loop
        from app.services.broadcaster import broadcast_loop
        from app.database import AsyncSessionLocal
        asyncio.create_task(
            broadcast_loop(AsyncSessionLocal),
            name="metrics-broadcaster",
        )
        logger.info("Metrics broadcaster started")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("SmartDialer API shutting down")

    return app


app = create_app()
