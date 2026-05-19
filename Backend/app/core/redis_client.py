"""Shared Redis connection for OTP and other ephemeral state."""
from __future__ import annotations

import logging
from typing import Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    """Return a shared Redis client, or None if REDIS_URL is not configured."""
    global _redis_client
    if not settings.use_redis_for_otp:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        client.ping()
        _redis_client = client
        logger.info("Redis connection established for OTP storage")
    except redis.RedisError as exc:
        logger.error(
            "Redis unavailable (%s); OTP will use in-memory fallback (not safe with multiple Gunicorn workers)",
            exc,
        )
        return None
    return _redis_client
