from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date, datetime
from app.utils.timezone import today_ist


class CompanyHolidayCreate(BaseModel):
    date: date
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    is_recurring: Optional[bool] = True

    @field_validator('date')
    @classmethod
    def validate_holiday_date_not_past(cls, v: date) -> date:
        if v < today_ist():
            raise ValueError("Holiday date cannot be in the past. Please select today or a future date.")
        return v


class CompanyHolidayOut(BaseModel):
    id: int
    company_id: int = Field(..., gt=0, description="Company this holiday belongs to")
    date: date
    name: str
    description: Optional[str]
    is_recurring: bool
    created_at: datetime

    class Config:
        from_attributes = True


VALID_WEEKDAYS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
}
WEEKDAY_NAME_MAP = {
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
    "saturday": "Saturday",
    "sunday": "Sunday",
}


class DeptWeekOffRuleCreate(BaseModel):
    department: str = Field(..., min_length=1, max_length=100, description="Department name")
    days: List[str] = Field(..., min_length=1, description="List of weekday names e.g., ['Saturday', 'Sunday']")

    @field_validator('department')
    @classmethod
    def validate_department_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Department name cannot be empty.")
        return v.strip()

    @field_validator('days')
    @classmethod
    def validate_days(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one week-off day must be provided.")
        normalized_days: list[str] = []
        for d in v:
            cleaned = str(d).strip()
            if not cleaned:
                continue
            cleaned_lower = cleaned.lower()
            if cleaned_lower not in VALID_WEEKDAYS:
                raise ValueError(
                    f"Invalid day '{d}'. Must be a valid weekday name (e.g. Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday)."
                )
            canon = WEEKDAY_NAME_MAP[cleaned_lower]
            if canon not in normalized_days:
                normalized_days.append(canon)
        if not normalized_days:
            raise ValueError("At least one valid week-off day must be provided.")
        return normalized_days


class DeptWeekOffRuleOut(BaseModel):
    id: int
    company_id: int = Field(..., gt=0, description="Company this week-off rule belongs to")
    department: str
    days: List[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LeaveAllocationUpdate(BaseModel):
    total_annual_leave: int
    sick_leave_allocation: int
    casual_leave_allocation: int
    other_leave_allocation: int


class CalendarEvent(BaseModel):
    id: str
    title: str
    start: date
    end: Optional[date]
    type: str  # 'holiday', 'leave', 'weekoff'
    department: Optional[str] = None
    user_id: Optional[int] = None

    class Config:
        from_attributes = True


class CompanyHolidayNotificationOut(BaseModel):
    notification_id: int
    user_id: int
    holiday_id: Optional[int] = None
    notification_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


