"""
Token-bucket rate limiter middleware using Redis as shared state.
Supports distributed rate limiting across multiple backend instances.
"""
import time
import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import get_settings
from app.db.redis_client import get_redis

log = structlog.get_logger(__name__)
settings = get_settings()

# Lua script for atomic token bucket check + decrement
_RATE_LIMIT_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1]) or capacity
local last_refill = tonumber(data[2]) or now

-- Refill tokens based on elapsed time
local elapsed = now - last_refill
local refill = elapsed * refill_rate
tokens = math.min(capacity, tokens + refill)

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 60)
    return 1  -- Allowed
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 60)
    return 0  -- Rejected
end
"""


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter. Only limits /api/v1/signals endpoint."""

    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/api/v1/ws"}

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip rate limiting for exempt paths
        if any(path.startswith(exempt) for exempt in self.EXEMPT_PATHS):
            return await call_next(request)

        # Only rate-limit signal ingestion
        if not path.startswith("/api/v1/signals"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        allowed = await self._check_rate_limit(client_ip)

        if not allowed:
            log.warning("rate_limit.exceeded", client=client_ip, path=path)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Max 10,000 signals/second.",
                    "retry_after": 1,
                },
                headers={"Retry-After": "1"},
            )

        return await call_next(request)

    async def _check_rate_limit(self, client_ip: str) -> bool:
        try:
            r = get_redis()
            key = f"ims:ratelimit:{client_ip}"
            now = time.time()
            result = await r.eval(
                _RATE_LIMIT_LUA,
                1,
                key,
                settings.rate_limit_requests,
                settings.rate_limit_requests / settings.rate_limit_window_seconds,
                now,
                1,
            )
            return bool(result)
        except Exception as exc:
            # If Redis is down, fail open (allow the request)
            log.error("rate_limiter.redis_error", error=str(exc))
            return True
