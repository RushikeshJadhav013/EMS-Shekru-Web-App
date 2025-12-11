"""
Timezone utilities for IST (Asia/Kolkata) conversion
"""
from datetime import datetime, date, time
import pytz
from typing import Optional, Union

# Application timezone - Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')
UTC = pytz.utc

def now_ist() -> datetime:
    """Get current datetime in IST timezone"""
    return datetime.now(IST)

def today_ist() -> date:
    """Get current date in IST timezone"""
    return now_ist().date()

def utc_to_ist(utc_dt: datetime) -> datetime:
    """Convert UTC datetime to IST"""
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        utc_dt = UTC.localize(utc_dt)
    return utc_dt.astimezone(IST)

def ist_to_utc(ist_dt: datetime) -> datetime:
    """Convert IST datetime to UTC for database storage"""
    if ist_dt is None:
        return None
    if ist_dt.tzinfo is None:
        ist_dt = IST.localize(ist_dt)
    return ist_dt.astimezone(UTC)

def localize_ist(naive_dt: datetime) -> datetime:
    """Add IST timezone info to naive datetime"""
    if naive_dt is None:
        return None
    if naive_dt.tzinfo is not None:
        return naive_dt
    return IST.localize(naive_dt)

def make_ist_datetime(date_obj: date, time_obj: time) -> datetime:
    """Create IST datetime from date and time objects"""
    naive_dt = datetime.combine(date_obj, time_obj)
    return IST.localize(naive_dt)

def ist_start_of_day(date_obj: Optional[date] = None) -> datetime:
    """Get start of day (00:00:00) in IST for given date or today"""
    if date_obj is None:
        date_obj = today_ist()
    return IST.localize(datetime.combine(date_obj, time.min))

def ist_end_of_day(date_obj: Optional[date] = None) -> datetime:
    """Get end of day (23:59:59) in IST for given date or today"""
    if date_obj is None:
        date_obj = today_ist()
    return IST.localize(datetime.combine(date_obj, time.max))

def format_ist_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime in IST timezone"""
    if dt is None:
        return ""
    ist_dt = utc_to_ist(dt) if dt.tzinfo == UTC else dt
    return ist_dt.strftime(format_str)

def parse_ist_datetime(dt_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """Parse datetime string as IST"""
    naive_dt = datetime.strptime(dt_str, format_str)
    return IST.localize(naive_dt)

def get_today_bounds_ist() -> tuple[datetime, datetime]:
    """Get today's start and end bounds in IST, converted to UTC for database queries"""
    today = today_ist()
    start_ist = ist_start_of_day(today)
    end_ist = ist_end_of_day(today)
    return ist_to_utc(start_ist), ist_to_utc(end_ist)

def get_date_bounds_ist(date_obj: date) -> tuple[datetime, datetime]:
    """Get date's start and end bounds in IST, converted to UTC for database queries"""
    start_ist = ist_start_of_day(date_obj)
    end_ist = ist_end_of_day(date_obj)
    return ist_to_utc(start_ist), ist_to_utc(end_ist)