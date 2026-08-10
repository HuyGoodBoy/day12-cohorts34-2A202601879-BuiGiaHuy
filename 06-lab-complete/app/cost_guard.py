"""
Cost guard — Redis per-user monthly budget.

Spec (CODE_LAB.md § 4.4)
────────────────────────
- Each user has a monthly budget (USD).
- Track spending in Redis (key: budget:<user_id>:<YYYY-MM>).
- Reset on the first day of a new month (TTL 32 days).

Returns / raises
────────────────
- Returns estimated cost when within budget.
- Raises HTTPException 402 Payment Required when budget exceeded.
- Falls back to in-memory tracker if Redis is unavailable (dev only).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

# OpenAI gpt-4o-mini pricing (USD per 1K tokens) — for reference
_PRICE_INPUT = 0.00015
_PRICE_OUTPUT = 0.0006

# Fallback in-memory store (only used when Redis is down)
_memory_cost: dict[str, float] = {}
_memory_month: str = ""


def _client():
    import redis
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1000) * _PRICE_INPUT + (output_tokens / 1000) * _PRICE_OUTPUT


def check_and_record_cost(
    user_id: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """
    Atomically check budget and record cost.

    Args:
        user_id: bucket key (truncated api_key prefix).
        input_tokens: tokens consumed by the prompt.
        output_tokens: tokens produced by the model.

    Returns:
        The amount (USD) that was just recorded.

    Raises:
        HTTPException 402 if the user would exceed the monthly budget.
    """
    cost = estimate_cost(input_tokens, output_tokens)
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    redis_key = f"budget:{user_id}:{month_key}"
    budget = settings.daily_budget_usd  # keeping name for backward compat

    # ── Try Redis ─────────────────────────────────────
    try:
        r = _client()
        # Lua script for atomicity: read current, compare, then INCRBYFLOAT
        lua = """
        local current = tonumber(redis.call('GET', KEYS[1]) or '0')
        local cost = tonumber(ARGV[1])
        local budget = tonumber(ARGV[2])
        if current + cost > budget then
            return -1
        end
        redis.call('INCRBYFLOAT', KEYS[1], cost)
        redis.call('EXPIRE', KEYS[1], 32 * 24 * 3600)
        return current + cost
        """
        result = r.eval(lua, 1, redis_key, str(cost), str(budget))
        if result == -1:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Monthly budget for {month_key} exceeded "
                    f"(${budget:.2f}). Please contact admin."
                ),
            )
        return cost
    except HTTPException:
        raise
    except Exception as exc:
        # Fallback to in-memory
        logger.warning(f"Cost guard Redis unavailable, using in-memory fallback: {exc}")
        global _memory_month
        if _memory_month != month_key:
            _memory_month = month_key
            _memory_cost.clear()
        current = _memory_cost.get(user_id, 0.0)
        if current + cost > budget:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Monthly budget for {month_key} exceeded (in-memory).",
            )
        _memory_cost[user_id] = current + cost
        return cost


def get_current_spend(user_id: str) -> float:
    """Read current spend (used by /metrics). Falls back to in-memory."""
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    redis_key = f"budget:{user_id}:{month_key}"
    try:
        r = _client()
        val = r.get(redis_key)
        return float(val) if val else 0.0
    except Exception:
        return _memory_cost.get(user_id, 0.0)
