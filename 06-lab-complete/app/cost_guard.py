"""
Cost Guard — Budget protection for LLM API calls.

Prevents runaway spending by tracking estimated token costs.

Design:
  - Daily budget per deployment (configurable via DAILY_BUDGET_USD env var)
  - Auto-resets at midnight (date string comparison)
  - Warning log at 80% budget utilization
  - Hard block at 100% with HTTP 503

Production improvement: use Redis to persist across restarts and
share state between multiple instances.
"""
import time
import logging

from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# In-memory cost tracking
# ─────────────────────────────────────────────────────────
_daily_cost: float = 0.0
_cost_reset_day: str = time.strftime("%Y-%m-%d")

# GPT-4o-mini pricing (as of 2024)
INPUT_COST_PER_1K = 0.00015   # $0.15 per 1M input tokens
OUTPUT_COST_PER_1K = 0.0006   # $0.60 per 1M output tokens


def _maybe_reset_day() -> None:
    """Reset daily cost if the day has changed."""
    global _daily_cost, _cost_reset_day
    today = time.strftime("%Y-%m-%d")
    if today != _cost_reset_day:
        logger.info(f"Daily cost reset: ${_daily_cost:.4f} → $0.00 (new day: {today})")
        _daily_cost = 0.0
        _cost_reset_day = today


def check_budget() -> None:
    """
    Check if daily budget is still available.

    Raises:
        HTTPException 503: If daily budget is exhausted.
    """
    _maybe_reset_day()
    if _daily_cost >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=503,
            detail=f"Daily budget exhausted (${settings.daily_budget_usd:.2f}). Try tomorrow.",
        )


def record_cost(input_tokens: int = 0, output_tokens: int = 0) -> float:
    """
    Record token usage and calculate cost.

    Args:
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens used.

    Returns:
        The cost of this particular call in USD.
    """
    global _daily_cost
    _maybe_reset_day()

    cost = (input_tokens / 1000) * INPUT_COST_PER_1K + \
           (output_tokens / 1000) * OUTPUT_COST_PER_1K
    _daily_cost += cost

    # Warning at 80% budget
    utilization = _daily_cost / settings.daily_budget_usd
    if utilization >= 0.8:
        logger.warning(
            f"Budget alert: ${_daily_cost:.4f} / ${settings.daily_budget_usd:.2f} "
            f"({utilization * 100:.1f}% used)"
        )

    return cost


def get_usage() -> dict:
    """Return current daily cost usage stats."""
    _maybe_reset_day()
    return {
        "daily_cost_usd": round(_daily_cost, 4),
        "daily_budget_usd": settings.daily_budget_usd,
        "budget_used_pct": round(_daily_cost / settings.daily_budget_usd * 100, 1),
        "budget_remaining_usd": round(settings.daily_budget_usd - _daily_cost, 4),
    }
