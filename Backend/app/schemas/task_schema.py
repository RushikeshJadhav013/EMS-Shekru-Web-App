from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[str] = "Pending"
    due_date: Optional[date] = None
    priority: Optional[str] = "Medium"

class TaskCreate(TaskBase):
    assigned_to: int
    assigned_by: int

class TaskOut(TaskBase):
    task_id: int
    assigned_to: int
    assigned_by: int
    created_at: Optional[datetime] = None
    last_passed_by: Optional[int] = None
    last_passed_to: Optional[int] = None
    last_pass_note: Optional[str] = None
    last_passed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    due_date: Optional[date] = None


class TaskPassRequest(BaseModel):
    new_assignee_id: int
    note: Optional[str] = None


class TaskHistoryOut(BaseModel):
    id: int
    task_id: int
    user_id: int
    action: str
    details: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskNotificationOut(BaseModel):
    notification_id: int
    user_id: int
    task_id: int
    notification_type: str
    title: str
    message: str
    pass_details: Optional[dict] = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}

