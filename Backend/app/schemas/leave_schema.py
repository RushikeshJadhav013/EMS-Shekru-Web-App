from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class LeaveBase(BaseModel):
    start_date: date
    end_date: date
    reason: Optional[str] = None
    status: Optional[str] = "Pending"
    leave_type: str = "annual"


class LeaveCreate(LeaveBase):
    employee_id: str


class LeaveOut(LeaveBase):
    leave_id: int
    user_id: int

    model_config = {"from_attributes": True}


class LeaveWithUserOut(LeaveOut):
    employee_id: str
    name: str
    department: Optional[str] = None
    role: Optional[str] = None


class LeaveUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reason: Optional[str] = None
    leave_type: Optional[str] = None


class LeaveBalanceItem(BaseModel):
    leave_type: str
    allocated: int
    used: int
    remaining: int


class LeaveBalanceResponse(BaseModel):
    balances: list[LeaveBalanceItem]


class LeaveNotificationOut(BaseModel):
    notification_id: int
    user_id: int
    leave_id: int
    notification_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}