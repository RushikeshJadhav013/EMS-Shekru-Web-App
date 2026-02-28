from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class CompanyHolidayCreate(BaseModel):
    date: date
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    is_recurring: Optional[bool] = True


class CompanyHolidayOut(BaseModel):
    id: int
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


