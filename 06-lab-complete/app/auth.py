"""
Authentication module — API Key verification.

Supports:
  - X-API-Key header validation
  - Extensible to JWT (see 04-api-gateway/production/auth.py)
"""
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

# ─────────────────────────────────────────────────────────
# API Key Authentication
# ─────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify the API key from X-API-Key header.

    Returns:
        The API key string if valid (used as a "user_id" bucket).

    Raises:
        HTTPException 401: If key is missing or invalid.
    """
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    return api_key
