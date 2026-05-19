import random
from datetime import timedelta
from typing import Optional

import redis

from app.core.config import settings
from app.core.redis_client import get_redis
from app.utils.timezone import now_ist
import logging

logger = logging.getLogger(__name__)

# In-memory fallback when REDIS_URL is unset (local dev without Redis)
OTP_STORE: dict = {}


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _otp_redis_key(email: str) -> str:
    return f"{settings.OTP_REDIS_KEY_PREFIX}{_normalize_email(email)}"


def _count_active_otps_redis() -> int:
    client = get_redis()
    if not client:
        return 0
    return sum(1 for _ in client.scan_iter(match=f"{settings.OTP_REDIS_KEY_PREFIX}*"))


def generate_otp(email: str) -> int:
    """Generate OTP based on environment settings; store in Redis (or memory fallback)."""
    email_key = _normalize_email(email)
    if settings.should_use_fixed_otp:
        otp = int(settings.TESTING_OTP)
        logger.info(
            "Using fixed OTP %s for email %s in %s environment",
            otp,
            email_key,
            settings.ENVIRONMENT,
        )
    else:
        otp = random.randint(100000, 999999)
        logger.info(
            "Generated random OTP for email %s in %s environment",
            email_key,
            settings.ENVIRONMENT,
        )

    client = get_redis()
    if client:
        key = _otp_redis_key(email_key)
        client.set(key, str(otp), ex=settings.OTP_EXPIRY_SECONDS)
        logger.debug("OTP stored in Redis key=%s ttl=%ss", key, settings.OTP_EXPIRY_SECONDS)
    else:
        if settings.is_production:
            logger.warning(
                "REDIS_URL not set in production; OTP stored in process memory (not shared across workers)"
            )
        OTP_STORE[email_key] = {
            "otp": otp,
            "expiry": now_ist() + timedelta(seconds=settings.OTP_EXPIRY_SECONDS),
            "environment": settings.ENVIRONMENT,
        }
    return otp


def verify_otp(email: str, otp: int) -> bool:
    """Verify OTP with environment-aware logic."""
    email_key = _normalize_email(email)

    if settings.should_use_fixed_otp and otp == int(settings.TESTING_OTP):
        logger.info(
            "Accepted testing OTP for email %s in %s environment (no record required)",
            email_key,
            settings.ENVIRONMENT,
        )
        _delete_otp(email_key)
        return True

    client = get_redis()
    if client:
        return _verify_otp_redis(client, email_key, otp)
    return _verify_otp_memory(email_key, otp)


def _verify_otp_redis(client: redis.Redis, email_key: str, otp: int) -> bool:
    key = _otp_redis_key(email_key)
    try:
        stored = client.get(key)
    except redis.RedisError as exc:
        logger.error("Redis GET failed for %s: %s", key, exc)
        return False

    if stored is None:
        logger.warning("No OTP record found for email %s", email_key)
        return False

    try:
        expected = int(stored)
    except ValueError:
        logger.error("Invalid OTP value in Redis for key %s", key)
        client.delete(key)
        return False

    if expected != otp:
        logger.warning("Invalid OTP for email %s", email_key)
        return False

    client.delete(key)
    logger.info("OTP verified successfully for email %s in %s", email_key, settings.ENVIRONMENT)
    return True


def _verify_otp_memory(email_key: str, otp: int) -> bool:
    record = OTP_STORE.get(email_key)
    if not record:
        logger.warning("No OTP record found for email %s", email_key)
        return False

    if record["otp"] != otp:
        logger.warning("Invalid OTP for email %s", email_key)
        return False

    if now_ist() > record["expiry"]:
        logger.warning("OTP expired for email %s", email_key)
        del OTP_STORE[email_key]
        return False

    logger.info("OTP verified successfully for email %s in %s", email_key, settings.ENVIRONMENT)
    del OTP_STORE[email_key]
    return True


def _delete_otp(email_key: str) -> None:
    client = get_redis()
    if client:
        try:
            client.delete(_otp_redis_key(email_key))
        except redis.RedisError as exc:
            logger.warning("Redis DELETE failed for %s: %s", email_key, exc)
    OTP_STORE.pop(email_key, None)


def get_otp_info(email: str) -> dict:
    """Get OTP information for debugging (only in non-production)."""
    if settings.is_production:
        return {"error": "OTP info not available in production"}

    email_key = _normalize_email(email)
    client = get_redis()
    if client:
        key = _otp_redis_key(email_key)
        stored = client.get(key)
        if not stored:
            return {"error": "No OTP found"}
        ttl = client.ttl(key)
        return {
            "email": email_key,
            "otp": int(stored),
            "storage": "redis",
            "ttl_seconds": ttl,
            "environment": settings.ENVIRONMENT,
            "is_expired": ttl < 0,
            "time_remaining": max(0, ttl),
        }

    record = OTP_STORE.get(email_key)
    if not record:
        return {"error": "No OTP found"}

    return {
        "email": email_key,
        "otp": record["otp"],
        "storage": "memory",
        "expiry": record["expiry"].isoformat(),
        "environment": record["environment"],
        "is_expired": now_ist() > record["expiry"],
        "time_remaining": max(0, (record["expiry"] - now_ist()).total_seconds()),
    }


def clear_all_otps() -> None:
    """Clear all OTPs (useful for testing)."""
    client = get_redis()
    if client:
        deleted = 0
        for key in client.scan_iter(match=f"{settings.OTP_REDIS_KEY_PREFIX}*"):
            client.delete(key)
            deleted += 1
        logger.info("Cleared %s OTP keys from Redis", deleted)
    OTP_STORE.clear()
    logger.info("In-memory OTP store cleared")


def get_environment_info() -> dict:
    """Get current environment information for debugging."""
    active = _count_active_otps_redis() if settings.use_redis_for_otp else len(OTP_STORE)
    return {
        "environment": settings.ENVIRONMENT,
        "should_use_fixed_otp": settings.should_use_fixed_otp,
        "should_send_email": settings.should_send_email,
        "testing_otp": settings.TESTING_OTP if settings.should_use_fixed_otp else None,
        "enable_email_otp": settings.ENABLE_EMAIL_OTP,
        "redis_otp_enabled": settings.use_redis_for_otp,
        "active_otps": active,
    }
