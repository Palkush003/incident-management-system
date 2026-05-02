"""Health check endpoint — returns status of all dependencies."""
from fastapi import APIRouter
from app.db.postgres import get_db
from app.db.mongodb import get_mongodb
from app.db.redis_client import get_redis
from app.utils.metrics import metrics_collector
from sqlalchemy import text
import structlog

log = structlog.get_logger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health", summary="System health check")
async def health_check():
    checks = {}

    # PostgreSQL
    try:
        async with get_db() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "healthy"
    except Exception as exc:
        checks["postgres"] = f"unhealthy: {exc}"

    # MongoDB
    try:
        db = get_mongodb()
        await db.command("ping")
        checks["mongodb"] = "healthy"
    except Exception as exc:
        checks["mongodb"] = f"unhealthy: {exc}"

    # Redis
    try:
        r = get_redis()
        await r.ping()
        checks["redis"] = "healthy"
    except Exception as exc:
        checks["redis"] = f"unhealthy: {exc}"

    snap = metrics_collector.snapshot()
    overall = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"

    return {
        "status": overall,
        "dependencies": checks,
        "metrics": snap,
        "websocket_connections": 0,  # Updated via ws_manager
    }
