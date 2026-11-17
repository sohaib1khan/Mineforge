"""Health and readiness endpoints."""

from fastapi import APIRouter

from app import __version__
from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict[str, str]:
    """Return a simple liveness payload for load balancers and CI."""

    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": __version__,
    }
