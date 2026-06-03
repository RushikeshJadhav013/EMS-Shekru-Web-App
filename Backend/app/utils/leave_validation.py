"""Shared leave request validation (overlap, unpaid windows, duration)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.leave import Leave
from app.utils.timezone import now_ist

UNPAID_LEAVE_TYPE = "unpaid"
HALF_DAY_DURATION = 0.5
FULL_DAY_DURATION = 1.0
VALID_LEAVE_SESSIONS = frozenset({"before_lunch", "after_lunch"})


def is_unpaid_leave(leave_type: str | None) -> bool:
    return (leave_type or "").strip().lower() == UNPAID_LEAVE_TYPE


def _to_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def _duration_days_value(leave: Leave | object) -> float:
    raw = getattr(leave, "duration_days", None)
    if raw is None:
        return FULL_DAY_DURATION
    return float(raw)


def is_half_day_leave(leave: Leave | object) -> bool:
    return _duration_days_value(leave) == HALF_DAY_DURATION


def validate_unpaid_request_window(start: date) -> None:
    """
    Unpaid leave may be requested only for today or tomorrow (IST).
    Tomorrow may be requested on the day before (today).
    """
    today = now_ist().date()
    latest = today + timedelta(days=1)
    if start < today:
        raise ValueError(
            "Unpaid leave cannot be requested for past dates. "
            "You may apply for today or tomorrow only."
        )
    if start > latest:
        raise ValueError(
            "Unpaid leave can only be requested for today or the next calendar day."
        )


def validate_leave_shape(
    *,
    leave_type: str,
    start_date: date,
    end_date: date,
    duration_days: float,
    leave_session: Optional[str],
) -> tuple[float, Optional[str]]:
    """Normalize and validate duration/session for a leave request."""
    leave_type = leave_type.strip().lower()
    session = (leave_session or "").strip().lower() or None

    if duration_days not in (FULL_DAY_DURATION, HALF_DAY_DURATION):
        raise ValueError("duration_days must be 1.0 (full day) or 0.5 (half day).")

    if not is_unpaid_leave(leave_type):
        if duration_days != FULL_DAY_DURATION:
            raise ValueError("Only unpaid leave supports half-day duration.")
        if session is not None:
            raise ValueError("leave_session is only valid for unpaid half-day leave.")
        return FULL_DAY_DURATION, None

    if duration_days == HALF_DAY_DURATION:
        if start_date != end_date:
            raise ValueError("Half-day unpaid leave must use the same start and end date.")
        if session not in VALID_LEAVE_SESSIONS:
            raise ValueError(
                "Half-day unpaid leave requires leave_session: 'before_lunch' or 'after_lunch'."
            )
        validate_unpaid_request_window(start_date)
        return HALF_DAY_DURATION, session

    if session is not None:
        raise ValueError("Full-day unpaid leave must not include leave_session.")
    validate_unpaid_request_window(start_date)
    return FULL_DAY_DURATION, None


def compute_chargeable_days(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    duration_days: float = FULL_DAY_DURATION,
) -> float:
    if duration_days == HALF_DAY_DURATION:
        return HALF_DAY_DURATION
    start = _to_date(start_date)
    end = _to_date(end_date)
    calendar_days = (end - start).days + 1
    return float(calendar_days if calendar_days > 0 else 0)


def _iter_dates_in_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def scopes_on_date(leave: Leave, day: date) -> set[str]:
    """Return coverage scopes for a leave on a given calendar day."""
    start = _to_date(leave.start_date)
    end = _to_date(leave.end_date)
    if day < start or day > end:
        return set()

    if is_unpaid_leave(leave.leave_type) and is_half_day_leave(leave):
        session = (leave.leave_session or "").strip().lower()
        if session in VALID_LEAVE_SESSIONS and day == start:
            return {session}
        return set()

    return {"full"}


def scopes_conflict(left: set[str], right: set[str]) -> bool:
    if not left or not right:
        return False
    if "full" in left or "full" in right:
        return True
    return bool(left & right)


def leaves_conflict(proposed: Leave | dict, existing: Leave) -> bool:
    """True if two pending/approved leaves cannot coexist."""
    if isinstance(proposed, dict):
        p_start = _to_date(proposed["start_date"])
        p_end = _to_date(proposed["end_date"])
        p_type = proposed.get("leave_type", "")
        p_duration = proposed.get("duration_days", FULL_DAY_DURATION)
        p_session = proposed.get("leave_session")

        class _Proposed:
            start_date = proposed["start_date"]
            end_date = proposed["end_date"]
            leave_type = p_type
            duration_days = p_duration
            leave_session = p_session

        proposed_leave = _Proposed()
    else:
        proposed_leave = proposed
        p_start = _to_date(proposed_leave.start_date)
        p_end = _to_date(proposed_leave.end_date)

    e_start = _to_date(existing.start_date)
    e_end = _to_date(existing.end_date)
    overlap_start = max(p_start, e_start)
    overlap_end = min(p_end, e_end)
    if overlap_start > overlap_end:
        return False

    for day in _iter_dates_in_range(overlap_start, overlap_end):
        if scopes_conflict(scopes_on_date(proposed_leave, day), scopes_on_date(existing, day)):
            return True
    return False


def find_conflicting_leave(
    db: Session,
    *,
    user_id: int,
    company_id: int,
    start_date: datetime,
    end_date: datetime,
    leave_type: str,
    duration_days: float,
    leave_session: Optional[str],
    exclude_leave_id: Optional[int] = None,
) -> Optional[Leave]:
    proposed = {
        "start_date": start_date,
        "end_date": end_date,
        "leave_type": leave_type,
        "duration_days": duration_days,
        "leave_session": leave_session,
    }
    q = db.query(Leave).filter(
        Leave.user_id == user_id,
        Leave.company_id == company_id,
        Leave.status.in_(["Pending", "Approved"]),
        Leave.start_date <= end_date,
        Leave.end_date >= start_date,
    )
    if exclude_leave_id is not None:
        q = q.filter(Leave.leave_id != exclude_leave_id)

    for existing in q.all():
        if leaves_conflict(proposed, existing):
            return existing
    return None


def validate_advance_notice(
    *,
    leave_type: str,
    start_dt: datetime,
    shift_start_time_resolver,
) -> None:
    """
    Sick: shift-based window. Unpaid: today/tomorrow only (handled in shape).
    Others: 24 hours minimum advance notice.
    """
    leave_type = leave_type.strip().lower()
    if is_unpaid_leave(leave_type):
        validate_unpaid_request_window(start_dt.date())
        return

    now = now_ist()
    hours_difference = (start_dt - now).total_seconds() / 3600

    if leave_type == "sick":
        shift_start_time = shift_start_time_resolver(start_dt.date())
        if shift_start_time is None:
            raise ValueError(
                "Sick leave cannot be validated because office/shift start time is not configured."
            )
        shift_start_dt = datetime.combine(start_dt.date(), shift_start_time)
        shift_hours_difference = (shift_start_dt - now).total_seconds() / 3600
        if shift_hours_difference < 0:
            raise ValueError("Sick leave cannot be applied for past dates.")
        if shift_hours_difference > 24:
            raise ValueError(
                "Sick leave cannot be applied for future dates. "
                "It must be applied only within 24 hours of the start date."
            )
        if shift_hours_difference < 2:
            raise ValueError(
                "Sick leave cannot be applied within 2 hours of the start date."
            )
        return

    if hours_difference < 24:
        raise ValueError(
            "Leave requests (except sick and unpaid leave) must be submitted at least 24 hours in advance."
        )


def unpaid_leave_display_suffix(
    leave_type: str,
    duration_days: float,
    leave_session: Optional[str],
) -> str:
    if not is_unpaid_leave(leave_type):
        return ""
    if duration_days == HALF_DAY_DURATION:
        session = (leave_session or "").replace("_", " ").title()
        return f" (Half day – {session})" if session else " (Half day)"
    return " (Full day)"
