from pydantic import BaseModel, Field, validator
from datetime import time, date, datetime
from typing import Optional, List


class ShiftBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Shift name (e.g., Morning Shift, Evening Shift)")
    start_time: str = Field(..., pattern=r"^(?:2[0-3]|[01]?[0-9]):[0-5][0-9]$", description="Start time in HH:MM format")
    end_time: str = Field(..., pattern=r"^(?:2[0-3]|[01]?[0-9]):[0-5][0-9]$", description="End time in HH:MM format")
    department: Optional[str] = Field(None, max_length=255, description="Department name, or null for global shifts")
    description: Optional[str] = Field(None, max_length=500)
    is_active: bool = Field(True, description="Whether the shift is active")

    @validator('start_time', 'end_time', pre=True)
    def parse_time_string(cls, v):
        if isinstance(v, time):
            return v.strftime("%H:%M")
        return v

    @validator('end_time')
    def end_time_must_be_after_start_time(cls, v, values):
        if 'start_time' in values and v:
            start = datetime.strptime(values['start_time'], "%H:%M").time()
            end = datetime.strptime(v, "%H:%M").time()
            start_minutes = start.hour * 60 + start.minute
            end_minutes = end.hour * 60 + end.minute
            duration = end_minutes - start_minutes
            if duration <= 0:
                duration += 24 * 60  # Allow overnight shifts
            if duration <= 0:
                raise ValueError('Shift duration must be greater than 0 minutes')
        return v


class ShiftCreate(ShiftBase):
    pass


class ShiftUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    start_time: Optional[str] = Field(None, pattern=r"^(?:2[0-3]|[01]?[0-9]):[0-5][0-9]$")
    end_time: Optional[str] = Field(None, pattern=r"^(?:2[0-3]|[01]?[0-9]):[0-5][0-9]$")
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

    @validator('end_time')
    def end_time_must_be_after_start_time_update(cls, v, values):
        if 'start_time' in values and v and values['start_time']:
            start = datetime.strptime(values['start_time'], "%H:%M").time()
            end = datetime.strptime(v, "%H:%M").time()
            start_minutes = start.hour * 60 + start.minute
            end_minutes = end.hour * 60 + end.minute
            duration = end_minutes - start_minutes
            if duration <= 0:
                duration += 24 * 60  # Allow overnight shifts
            if duration <= 0:
                raise ValueError('Shift duration must be greater than 0 minutes')
        return v


class ShiftOut(ShiftBase):
    shift_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ShiftAssignmentBase(BaseModel):
    user_id: int = Field(..., description="User ID to assign")
    shift_id: int = Field(..., description="Shift ID to assign")
    assignment_date: date = Field(..., description="Date for which the shift is assigned")
    notes: Optional[str] = Field(None, max_length=500)


class ShiftAssignmentCreate(ShiftAssignmentBase):
    pass


class ShiftAssignmentBulkCreate(BaseModel):
    user_ids: List[int] = Field(..., description="List of user IDs to assign")
    shift_id: int = Field(..., description="Shift ID to assign")
    assignment_date: date = Field(..., description="Date for which the shift is assigned")
    notes: Optional[str] = Field(None, max_length=500)


class ShiftAssignmentUpdate(BaseModel):
    shift_id: Optional[int] = None
    assignment_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=500)


class UserBasicInfo(BaseModel):
    user_id: int
    name: str
    email: str
    employee_id: Optional[str]
    department: Optional[str]
    designation: Optional[str]

    model_config = {"from_attributes": True}


class ShiftAssignmentOut(ShiftAssignmentBase):
    assignment_id: int
    assigned_by: Optional[int]
    is_reassigned: bool
    created_at: datetime
    updated_at: Optional[datetime]
    user: Optional[UserBasicInfo] = None
    shift: Optional[ShiftOut] = None

    model_config = {"from_attributes": True}


class ShiftScheduleView(BaseModel):
    """View model for shift schedule with user assignments"""
    shift: ShiftOut
    assignments: List[ShiftAssignmentOut]
    total_assigned: int
    available_slots: Optional[int] = None  # If shift has max capacity


class DepartmentShiftSchedule(BaseModel):
    """Shift schedule for a department"""
    department: str
    date: date
    shifts: List[ShiftScheduleView]
    users_on_leave: List[UserBasicInfo]  # Users on leave for this date
    unassigned_users: List[UserBasicInfo]  # Users not assigned to any shift


class DepartmentShiftScheduleRange(BaseModel):
    """Weekly shift schedule for a department"""
    department: str
    start_date: date
    end_date: date
    days: List[DepartmentShiftSchedule]


class ShiftNotificationOut(BaseModel):
    notification_id: int
    user_id: int
    shift_assignment_id: int
    notification_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    shift_assignment: Optional[ShiftAssignmentOut] = None

    model_config = {"from_attributes": True}


class UserShiftSchedule(BaseModel):
    """User's shift schedule for a date range"""
    user: UserBasicInfo
    assignments: List[ShiftAssignmentOut]
    upcoming_shifts: List[ShiftAssignmentOut]
    past_shifts: List[ShiftAssignmentOut]

