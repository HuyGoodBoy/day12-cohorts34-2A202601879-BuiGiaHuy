"""
Rate limiting — Redis sliding window (stateless, production-grade).

Algorithm
─────────
- ZADD timestamp_ms to a per-user sorted set
- ZREMRANGEBYSCORE to drop entries older than 60s
- ZCARD to count current window
- All inside a Redis pipeline → atomic

If Redis is unavailable, fail OPEN (allow request) — we never want
rate limiter outage to take down the API.
"""
from __future__ import annotations

import time
import logging
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


def _redis():
    """Lazy import so tests / dev without redis still work."""
    import redis
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


_r = None


def _client():
    global _r
    if _r is None:
        _r = _redis()
    return _r


def check_rate_limit(user_id: str) -> None:
    """
    Sliding-window rate limit per user.

    Args:
        user_id: bucket key (e.g. truncated api_key prefix)

    Raises:
        HTTPException 429 when limit exceeded.
    """
    limit = settings.rate_limit_per_minute
    now_ms = int(time.time() * 1000)
    member = f"{now_ms}-{time.time_ns()}-{user_id}"
    window_ms = 60_000
    key = f"rl:{user_id}"

    try:
        r = _client()
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, now_ms - window_ms)
        pipe.zadd(key, {member: now_ms})
        pipe.zcard(key)
        pipe.expire(key, 65)
        _, _, count, _ = pipe.execute()
    except Exception as exc:
        # Fail OPEN — log and allow the request.
        logger.warning(f"Rate limiter unavailable, allowing request: {exc}")
        return

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit} req/min. Try again shortly.",
            headers={"Retry-After": "60"},
        )
