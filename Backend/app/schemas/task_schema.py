from pydantic import BaseModel, Field, field_validator, constr
from datetime import datetime, date, timedelta
from typing import Optional, Literal

class TaskBase(BaseModel):
    title: constr(min_length=3, max_length=255, strip_whitespace=True) = Field(..., description="Task title (3-255 characters)")
    description: Optional[constr(max_length=2000, strip_whitespace=True)] = Field(None, description="Task description (max 2000 characters)")
    status: Optional[Literal['Pending', 'In Progress', 'Completed', 'On Hold', 'Cancelled']] = Field("Pending", description="Task status")
    due_date: Optional[date] = Field(None, description="Task due date")
    priority: Optional[Literal['Low', 'Medium', 'High', 'Urgent']] = Field("Medium", description="Task priority")

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is meaningful"""
        if not v or not v.strip():
            raise ValueError('Task title cannot be empty')
        if len(v.strip()) < 3:
            raise ValueError('Task title must be at least 3 characters')
        return v.strip()

    @field_validator('due_date')
    @classmethod
    def validate_due_date(cls, v: Optional[date]) -> Optional[date]:
        """Validate due date is reasonable"""
        if v is not None:
            if v < date(2000, 1, 1):
                raise ValueError('Due date cannot be before year 2000')
            # Allow tasks to be created with past due dates (for historical data)
            # but warn if too far in the future
            if v > date.today() + timedelta(days=3650):  # 10 years
                raise ValueError('Due date cannot be more than 10 years in the future')
        return v

class TaskCreate(TaskBase):
    assigned_to: int = Field(..., gt=0, description="User ID to assign task to")
    assigned_by: int = Field(..., gt=0, description="User ID who is assigning the task")

    @field_validator('assigned_to')
    @classmethod
    def validate_assigned_to(cls, v: int, info) -> int:
        """Validate assigned_to is different from assigned_by"""
        if 'assigned_by' in info.data and v == info.data['assigned_by']:
            raise ValueError('Cannot assign task to yourself')
        return v

class TaskOut(TaskBase):
    task_id: int = Field(..., gt=0, description="Unique task ID")
    assigned_to: int = Field(..., gt=0, description="Assigned to user ID")
    assigned_by: int = Field(..., gt=0, description="Assigned by user ID")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_passed_by: Optional[int] = Field(None, gt=0, description="Last user who passed the task")
    last_passed_to: Optional[int] = Field(None, gt=0, description="Last user task was passed to")
    last_pass_note: Optional[constr(max_length=500)] = Field(None, description="Note from last pass")
    last_passed_at: Optional[datetime] = Field(None, description="Timestamp of last pass")

    model_config = {"from_attributes": True}


class TaskUpdate(BaseModel):
    title: Optional[constr(min_length=3, max_length=255, strip_whitespace=True)] = Field(None, description="Updated title")
    description: Optional[constr(max_length=2000, strip_whitespace=True)] = Field(None, description="Updated description")
    assigned_to: Optional[int] = Field(None, gt=0, description="New assignee user ID")
    due_date: Optional[date] = Field(None, description="Updated due date")

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        """Validate title if provided"""
        if v is not None:
            if not v.strip():
                raise ValueError('Task title cannot be empty')
            if len(v.strip()) < 3:
                raise ValueError('Task title must be at least 3 characters')
        return v.strip() if v else v


class TaskPassRequest(BaseModel):
    new_assignee_id: int = Field(..., gt=0, description="User ID to pass task to")
    note: Optional[constr(min_length=5, max_length=500, strip_whitespace=True)] = Field(None, description="Note explaining the pass (5-500 characters)")

    @field_validator('note')
    @classmethod
    def validate_note(cls, v: Optional[str]) -> Optional[str]:
        """Validate note if provided"""
        if v is not None:
            v = v.strip()
            if len(v) < 5:
                raise ValueError('Pass note must be at least 5 characters if provided')
        return v


class TaskHistoryOut(BaseModel):
    id: int = Field(..., gt=0, description="History entry ID")
    task_id: int = Field(..., gt=0, description="Task ID")
    user_id: int = Field(..., gt=0, description="User ID who performed action")
    action: constr(min_length=1, max_length=100) = Field(..., description="Action performed")
    details: Optional[dict] = Field(None, description="Additional details")
    created_at: datetime = Field(..., description="Action timestamp")

    model_config = {"from_attributes": True}


class TaskNotificationOut(BaseModel):
    notification_id: int = Field(..., gt=0, description="Notification ID")
    user_id: int = Field(..., gt=0, description="User ID")
    task_id: int = Field(..., gt=0, description="Task ID")
    notification_type: constr(min_length=1, max_length=50) = Field(..., description="Notification type")
    title: constr(min_length=1, max_length=255) = Field(..., description="Notification title")
    message: constr(min_length=1, max_length=1000) = Field(..., description="Notification message")
    pass_details: Optional[dict] = Field(None, description="Task pass details")
    is_read: bool = Field(..., description="Read status")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}

