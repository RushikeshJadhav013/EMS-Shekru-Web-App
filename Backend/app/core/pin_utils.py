import re
import logging
from datetime import timedelta

from app.core.config import settings
from app.crud.user_crud import hash_password, verify_password
from app.db.models.user import User
from app.utils.timezone import now_ist

logger = logging.getLogger(__name__)

PIN_PATTERN = re.compile(r"^\d{4}$")
WEAK_PINS = frozenset(
    {
        "0000",
        "1111",
        "2222",
        "3333",
        "4444",
        "5555",
        "6666",
        "7777",
        "8888",
        "9999",
        "1234",
        "4321",
        "1212",
        "0123",
    }
)


def normalize_pin(pin: str) -> str:
    return str(pin).strip()


def validate_pin_format(pin: str) -> str:
    normalized = normalize_pin(pin)
    if not PIN_PATTERN.fullmatch(normalized):
        raise ValueError("PIN must be exactly 4 digits")
    return normalized


def validate_pin_for_set(pin: str) -> str:
    normalized = validate_pin_format(pin)
    if settings.should_use_fixed_pin and normalized == settings.TESTING_PIN:
        return normalized
    if normalized in WEAK_PINS:
        raise ValueError("PIN is too common. Please choose a different PIN.")
    return normalized


def hash_pin(pin: str) -> str:
    return hash_password(validate_pin_format(pin))


def verify_stored_pin(pin: str, pin_hash: str) -> bool:
    return verify_password(validate_pin_format(pin), pin_hash)


def is_user_pin_locked(user: User) -> bool:
    locked_until = getattr(user, "pin_locked_until", None)
    if locked_until is None:
        return False
    if now_ist() >= locked_until:
        return False
    return True


def verify_login_pin(user: User, pin: str) -> bool:
    normalized = normalize_pin(pin)
    if not getattr(user, "is_pin_set", False) or not getattr(user, "pin_hash", None):
        return False
    return verify_stored_pin(normalized, user.pin_hash)


def get_pin_lock_remaining_seconds(user: User) -> int:
    locked_until = getattr(user, "pin_locked_until", None)
    if locked_until is None:
        return 0
    remaining = (locked_until - now_ist()).total_seconds()
    return max(0, int(remaining))


def get_pin_environment_info() -> dict:
    return {
        "environment": settings.ENVIRONMENT,
        "should_use_fixed_pin": settings.should_use_fixed_pin,
        "testing_pin": settings.TESTING_PIN if settings.should_use_fixed_pin else None,
        "pin_max_attempts": settings.PIN_MAX_ATTEMPTS,
        "pin_lockout_minutes": settings.PIN_LOCKOUT_MINUTES,
    }
