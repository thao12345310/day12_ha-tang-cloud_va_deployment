"""
Rate Limiter — Sliding Window Counter algorithm.

In-memory implementation for simplicity.
Production: replace with Redis-backed sliding window for multi-instance support.

Algorithm:
  - Each user/key gets a deque of request timestamps.
  - On new request: evict timestamps older than 60s, then count.
  - If count >= limit → 429 Too Many Requests + Retry-After header.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import settings

# ─────────────────────────────────────────────────────────
# In-memory sliding window storage
# ─────────────────────────────────────────────────────────
_rate_windows: dict[str, deque] = defaultdict(deque)


def check_rate_limit(key: str) -> None:
    """
    Check rate limit for a given key (usually first 8 chars of API key).

    Args:
        key: Identifier for the rate limit bucket (e.g., user_id or api_key prefix).

    Raises:
        HTTPException 429: If rate limit is exceeded.
    """
    now = time.time()
    window = _rate_windows[key]

    # Evict timestamps outside the 60-second window
    while window and window[0] < now - 60:
        window.popleft()

    if len(window) >= settings.rate_limit_per_minute:
        retry_after = int(60 - (now - window[0])) if window else 60
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} req/min",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(settings.rate_limit_per_minute),
                "X-RateLimit-Remaining": "0",
            },
        )
    window.append(now)


def get_remaining(key: str) -> int:
    """Return number of remaining requests in the current window."""
    now = time.time()
    window = _rate_windows.get(key, deque())
    active = sum(1 for ts in window if ts > now - 60)
    return max(0, settings.rate_limit_per_minute - active)
