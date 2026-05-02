"""Async Redis client with hot-path caching and TimeSeries helpers."""
import json
from datetime import datetime
from typing import Any
import structlog
import redis.asyncio as aioredis
from app.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

_redis: aioredis.Redis | None = None

# ── Key Schemas ──────────────────────────────────────────────────────────────
DASHBOARD_KEY = "ims:dashboard:active"
METRICS_KEY = "ims:metrics:throughput"
DEBOUNCE_KEY_PREFIX = "ims:debounce:"
DEBOUNCE_COUNT_PREFIX = "ims:debounce:count:"
INCIDENT_CACHE_PREFIX = "ims:incident:"


async def init_redis() -> None:
    global _redis
    _redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )
    await _redis.ping()
    log.info("redis.initialized", host=settings.redis_host)


async def close_redis() -> None:
    if _redis:
        await _redis.aclose()
        log.info("redis.closed")


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis


# ── Dashboard Cache ──────────────────────────────────────────────────────────

async def cache_incident(work_item_id: str, data: dict[str, Any], ttl: int = 300) -> None:
    r = get_redis()
    key = f"{INCIDENT_CACHE_PREFIX}{work_item_id}"
    await r.setex(key, ttl, json.dumps(data, default=str))


async def get_cached_incident(work_item_id: str) -> dict[str, Any] | None:
    r = get_redis()
    key = f"{INCIDENT_CACHE_PREFIX}{work_item_id}"
    raw = await r.get(key)
    return json.loads(raw) if raw else None


async def invalidate_incident_cache(work_item_id: str) -> None:
    r = get_redis()
    await r.delete(f"{INCIDENT_CACHE_PREFIX}{work_item_id}")


async def set_dashboard_state(data: dict[str, Any]) -> None:
    r = get_redis()
    await r.setex(DASHBOARD_KEY, 60, json.dumps(data, default=str))


async def get_dashboard_state() -> dict[str, Any] | None:
    r = get_redis()
    raw = await r.get(DASHBOARD_KEY)
    return json.loads(raw) if raw else None


# ── Throughput TimeSeries ─────────────────────────────────────────────────────

async def record_signal_ingested() -> None:
    """Increment per-second signal counter in Redis."""
    r = get_redis()
    now_bucket = int(datetime.utcnow().timestamp())
    key = f"ims:ts:signals:{now_bucket}"
    await r.incr(key)
    await r.expire(key, 120)  # Keep for 2 minutes


async def get_throughput_series(last_n_seconds: int = 60) -> list[dict]:
    """Return the signal throughput for the past N seconds."""
    r = get_redis()
    now = int(datetime.utcnow().timestamp())
    pipeline = r.pipeline()
    for i in range(last_n_seconds):
        pipeline.get(f"ims:ts:signals:{now - i}")
    results = await pipeline.execute()
    return [
        {"timestamp": now - i, "count": int(v) if v else 0}
        for i, v in enumerate(results)
    ]


# ── Debounce Helpers ─────────────────────────────────────────────────────────

async def get_debounce_key(component_id: str) -> str | None:
    """Return the current work_item_id for a debounce window, or None."""
    r = get_redis()
    return await r.get(f"{DEBOUNCE_KEY_PREFIX}{component_id}")


async def set_debounce_key(component_id: str, work_item_id: str, ttl: int) -> None:
    r = get_redis()
    await r.setex(f"{DEBOUNCE_KEY_PREFIX}{component_id}", ttl, work_item_id)


async def increment_debounce_count(component_id: str, ttl: int) -> int:
    r = get_redis()
    key = f"{DEBOUNCE_COUNT_PREFIX}{component_id}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, ttl)
    return count
