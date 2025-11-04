from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class LeaveBase(BaseModel):
    start_date: date
    end_date: date
    reason: Optional[str] = None
    status: Optional[str] = "Pending"

class LeaveCreate(LeaveBase):
    employee_id: str

class LeaveOut(LeaveBase):
    leave_id: int
    employee_id: str
    created_at: datetime

    model_config = {"from_attributes": True}
