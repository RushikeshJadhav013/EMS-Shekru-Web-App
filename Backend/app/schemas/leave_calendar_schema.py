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


class DeptWeekOffRuleCreate(BaseModel):
    department: str
    days: List[str]  # list of weekday names e.g., ["Saturday", "Sunday"]


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


