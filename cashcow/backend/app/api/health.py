"""Health check route."""

from fastapi import APIRouter

from app.core.config import VERSION
from app.models.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Report that the server is up and which version is running."""
    return HealthResponse(status="ok", version=VERSION)
