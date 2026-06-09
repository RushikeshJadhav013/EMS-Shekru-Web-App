"""
Minimal IST-only time helpers.
All timestamps are naive datetimes representing IST (Asia/Kolkata).
"""
from datetime import datetime, date, time
from typing import Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Current wall-clock time in Asia/Kolkata as a naive datetime."""
    return datetime.now(IST).replace(tzinfo=None)


def today_ist() -> date:
    """Current calendar date in Asia/Kolkata."""
    return now_ist().date()

def ist_start_of_day(date_obj: Optional[date] = None) -> datetime:
    """Get start of day (00:00:00) in IST for given date or today."""
    if date_obj is None:
        date_obj = today_ist()
    return datetime.combine(date_obj, time.min)

def ist_end_of_day(date_obj: Optional[date] = None) -> datetime:
    """Get end of day (23:59:59.999999) in IST for given date or today."""
    if date_obj is None:
        date_obj = today_ist()
    return datetime.combine(date_obj, time.max)

def format_ist_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format naive IST datetime to string."""
    if dt is None:
        return ""
    return dt.strftime(format_str)

def parse_ist_datetime(dt_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """Parse string into naive IST datetime."""
    return datetime.strptime(dt_str, format_str)

def get_today_bounds_ist() -> tuple[datetime, datetime]:
    """Get today's start and end bounds in IST (naive)."""
    today = today_ist()
    return ist_start_of_day(today), ist_end_of_day(today)

def get_date_bounds_ist(date_obj: date) -> tuple[datetime, datetime]:
    """Get date's start and end bounds in IST (naive)."""
    return ist_start_of_day(date_obj), ist_end_of_day(date_obj)