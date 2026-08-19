"""Health check router."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Returns service health status."""
    return HealthResponse(status="ok", service="smartdialer-api", version="1.0.0")
