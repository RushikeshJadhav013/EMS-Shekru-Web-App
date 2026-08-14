"""Employment status helpers shared by auth and employee listing."""
from datetime import date, datetime
from typing import Any, Optional

from app.utils.timezone import today_ist


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def is_ex_employee(user: Any, on_date: Optional[date] = None) -> bool:
    """
    True when resignation_date is set and is on or before the given date (IST today by default).
    Matches employee list "ex-employee" filtering.
    """
    resignation_day = _as_date(getattr(user, "resignation_date", None))
    if resignation_day is None:
        return False
    return resignation_day <= (on_date or today_ist())
