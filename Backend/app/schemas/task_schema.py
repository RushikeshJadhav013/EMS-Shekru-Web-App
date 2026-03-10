from pydantic import BaseModel, Field, field_validator, constr
from datetime import datetime, date, timedelta
from typing import Optional, Literal, List
from app.enums import RoleEnum

class TaskBase(BaseModel):
    title: constr(min_length=3, max_length=255, strip_whitespace=True) = Field(..., description="Task title (3-255 characters)")
    description: Optional[constr(max_length=2000, strip_whitespace=True)] = Field(None, description="Task description (max 2000 characters)")
    status: Optional[Literal['Pending', 'In Progress', 'Overdue', 'Completed', 'Cancelled']] = Field("Pending", description="Task status")
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
            today = date.today()
            if v < today:
                raise ValueError('Due date cannot be in the past. Please select today or a future date.')
            if v > today + timedelta(days=3650):  # 10 years
                raise ValueError('Due date cannot be more than 10 years in the future')
        return v

class TaskCreate(TaskBase):
    assigned_to: int = Field(..., gt=0, description="User ID to assign task to")
    assigned_by: int = Field(..., gt=0, description="User ID who is assigning the task")
    # Note: self-assignment is allowed; role-based validation enforced in route handlers.
    project_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Optional project ID this task belongs to",
        example=None,
    )


class TaskBulkCreate(TaskBase):
    assigned_to_ids: List[int] = Field(
        ..., min_length=1, description="List of user IDs to assign the task to"
    )
    project_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Optional project ID this task belongs to",
        example=None,
    )

class TaskOut(BaseModel):
    task_id: int = Field(..., gt=0, description="Unique task ID")
    title: constr(min_length=3, max_length=255, strip_whitespace=True) = Field(..., description="Task title (3-255 characters)")
    description: Optional[constr(max_length=2000, strip_whitespace=True)] = Field(None, description="Task description (max 2000 characters)")
    status: Optional[Literal['Pending', 'In Progress', 'Overdue', 'Completed', 'Cancelled']] = Field("Pending", description="Task status")
    due_date: Optional[date] = Field(None, description="Task due date")
    priority: Optional[Literal['Low', 'Medium', 'High', 'Urgent']] = Field("Medium", description="Task priority")
    assigned_to: int = Field(..., gt=0, description="Assigned to user ID")
    assigned_by: int = Field(..., gt=0, description="Assigned by user ID")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_passed_by: Optional[int] = Field(None, gt=0, description="Last user who passed the task")
    last_passed_to: Optional[int] = Field(None, gt=0, description="Last user task was passed to")
    last_pass_note: Optional[constr(max_length=500)] = Field(None, description="Note from last pass")
    last_passed_at: Optional[datetime] = Field(None, description="Timestamp of last pass")
    assigned_to_name: Optional[str] = Field(None, description="Name of the assignee")
    assigned_by_name: Optional[str] = Field(None, description="Name of the task creator")
    assigned_by_role: Optional[RoleEnum] = Field(None, description="Role of the user who assigned the task")
    assigned_to_role: Optional[RoleEnum] = Field(None, description="Role of the user who is assigned the task")
    project_id: Optional[int] = Field(None, description="Project ID this task belongs to")

    model_config = {"from_attributes": True}


class TaskOutWithoutProject(TaskOut):
    """Task output variant that hides project_id in responses (used for non-project tasks)."""
    project_id: Optional[int] = Field(None, exclude=True)

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is meaningful"""
        if not v or not v.strip():
            raise ValueError('Task title cannot be empty')
        if len(v.strip()) < 3:
            raise ValueError('Task title must be at least 3 characters')
        return v.strip()

    # Note: No due_date validation for output - existing tasks may have past dates


class TaskUpdate(BaseModel):
    title: Optional[constr(min_length=3, max_length=255, strip_whitespace=True)] = Field(None, description="Updated title")
    description: Optional[constr(max_length=2000, strip_whitespace=True)] = Field(None, description="Updated description")
    assigned_to: Optional[int] = Field(None, gt=0, description="New assignee user ID")
    due_date: Optional[date] = Field(None, description="Updated due date")
    priority: Optional[Literal['Low', 'Medium', 'High', 'Urgent']] = Field(None, description="Updated task priority")
    project_id: Optional[int] = Field(
        None, gt=0, description="Updated project ID this task belongs to"
    )

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

    @field_validator('due_date')
    @classmethod
    def validate_due_date(cls, v: Optional[date]) -> Optional[date]:
        """Validate due date is reasonable"""
        if v is not None:
            today = date.today()
            if v < today:
                raise ValueError('Due date cannot be in the past. Please select today or a future date.')
            if v > today + timedelta(days=3650):  # 10 years
                raise ValueError('Due date cannot be more than 10 years in the future')
        return v


class TaskBulkUpdateFields(BaseModel):
    """Update fields for PUT /tasks/bulk. assigned_to is not allowed; use add_assigned_to_ids instead."""
    title: Optional[constr(min_length=3, max_length=255, strip_whitespace=True)] = Field(None, description="Updated title")
    description: Optional[constr(max_length=2000, strip_whitespace=True)] = Field(None, description="Updated description")
    # assigned_to: excluded from bulk update - use add_assigned_to_ids to add new assignees
    due_date: Optional[date] = Field(None, description="Updated due date")
    priority: Optional[Literal['Low', 'Medium', 'High', 'Urgent']] = Field(None, description="Updated task priority")

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError('Task title cannot be empty')
            if len(v.strip()) < 3:
                raise ValueError('Task title must be at least 3 characters')
        return v.strip() if v else v

    @field_validator('due_date')
    @classmethod
    def validate_due_date(cls, v: Optional[date]) -> Optional[date]:
        if v is not None:
            today = date.today()
            if v < today:
                raise ValueError('Due date cannot be in the past. Please select today or a future date.')
            if v > today + timedelta(days=3650):
                raise ValueError('Due date cannot be more than 10 years in the future')
        return v


class BulkTaskUpdate(BaseModel):
    task_ids: List[int] = Field(
        ..., min_length=1, description="List of task IDs to update"
    )
    updates: TaskBulkUpdateFields = Field(..., description="Fields to update for each task")

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

