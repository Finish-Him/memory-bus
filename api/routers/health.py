"""Health check router."""

from fastapi import APIRouter
from .services.database import DatabasePool

router = APIRouter()


@router.get("/health")
async def health_check():
    """Liveness probe."""
    return {"ok": True, "service": "memory-bus", "version": "0.1.0"}


@router.get("/health/ready")
async def readiness():
    """Readiness probe — checks database connectivity."""
    db = DatabasePool()
    connected = await db.health_check()
    return {
        "ok": connected,
        "database": connected,
        "service": "memory-bus",
    }
