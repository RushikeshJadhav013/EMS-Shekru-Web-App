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
    assigned_to: str
    assigned_by: str

class TaskOut(TaskBase):
    task_id: int
    assigned_to: str
    assigned_by: str
    created_at: datetime

    model_config = {"from_attributes": True}
