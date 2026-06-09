from pydantic import BaseModel, Field, field_validator, model_validator, constr
from datetime import date, datetime, timedelta
from typing import Optional, Literal

from app.utils.leave_validation import (
    FULL_DAY_DURATION,
    HALF_DAY_DURATION,
    is_unpaid_leave,
    validate_leave_shape,
)


class LeaveBase(BaseModel):
    start_date: date = Field(..., description="Leave start date")
    end_date: date = Field(..., description="Leave end date")
    reason: Optional[constr(min_length=10, max_length=500, strip_whitespace=True)] = Field(
        None, description="Leave reason (10-500 characters)"
    )
    leave_type: Literal['sick', 'casual', 'maternity', 'paternity', 'unpaid'] = Field(
        'sick', description="Type of leave"
    )
    duration_days: float = Field(
        FULL_DAY_DURATION,
        description="1.0 for full day; 0.5 for unpaid half day (before/after lunch)",
    )
    leave_session: Optional[Literal['before_lunch', 'after_lunch']] = Field(
        None,
        description="Required for unpaid half-day leave",
    )

    @field_validator('duration_days')
    @classmethod
    def validate_duration_days(cls, v: float) -> float:
        if v not in (FULL_DAY_DURATION, HALF_DAY_DURATION):
            raise ValueError('duration_days must be 1.0 or 0.5')
        return v

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v: date, info) -> date:
        """Validate end date is not before start date"""
        if 'start_date' in info.data:
            start_date = info.data['start_date']
            if v < start_date:
                raise ValueError('End date cannot be before start date')
            duration = info.data.get('duration_days', FULL_DAY_DURATION)
            if duration == HALF_DAY_DURATION and v != start_date:
                raise ValueError('Half-day leave must have the same start and end date')
            if duration == FULL_DAY_DURATION:
                span = (v - start_date).days + 1
                if span > 365:
                    raise ValueError('Leave duration cannot exceed 365 days')
        return v

    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v: date, info) -> date:
        """Validate start date is not too far in the past (non-unpaid)."""
        leave_type = info.data.get('leave_type')
        if leave_type and is_unpaid_leave(str(leave_type)):
            return v
        if v < date(2000, 1, 1):
            raise ValueError('Start date cannot be before year 2000')
        if v < date.today() - timedelta(days=30):
            raise ValueError('Cannot apply for leave more than 30 days in the past')
        return v

    @model_validator(mode='after')
    def validate_leave_combination(self) -> 'LeaveBase':
        try:
            duration, session = validate_leave_shape(
                leave_type=self.leave_type,
                start_date=self.start_date,
                end_date=self.end_date,
                duration_days=float(self.duration_days),
                leave_session=self.leave_session,
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        self.duration_days = duration
        self.leave_session = session  # type: ignore[assignment]
        return self

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: Optional[str]) -> Optional[str]:
        """Validate reason is meaningful"""
        if v is not None:
            v = v.strip()
            if len(v) < 10:
                raise ValueError('Leave reason must be at least 10 characters')
            if len(v) > 500:
                raise ValueError('Leave reason cannot exceed 500 characters')
        return v


class LeaveCreate(LeaveBase):
    """Request schema for creating a leave — uses authenticated user, no employee_id in request body."""
    pass


class LeaveOut(LeaveBase):
    leave_id: int = Field(..., gt=0, description="Unique leave ID")
    company_id: int = Field(..., gt=0, description="Company this leave belongs to")
    user_id: int = Field(..., gt=0, description="User ID")
    status: Optional[str] = Field("Pending", description="Leave status")

    model_config = {"from_attributes": True}


class LeaveWithUserOut(LeaveOut):
    employee_id: str
    name: constr(min_length=1, max_length=255)
    department: Optional[str] = None
    role: Optional[str] = None


class LeaveHistoryOut(BaseModel):
    """Schema for displaying historical leave data without strict validation"""
    leave_id: int = Field(..., gt=0, description="Unique leave ID")
    company_id: int = Field(..., gt=0, description="Company this leave belongs to")
    user_id: int = Field(..., gt=0, description="User ID")
    start_date: date = Field(..., description="Leave start date")
    end_date: date = Field(..., description="Leave end date")
    reason: Optional[str] = Field(None, description="Leave reason")
    status: Optional[str] = Field("Pending", description="Leave status")
    leave_type: str = Field("annual", description="Type of leave")
    duration_days: float = Field(FULL_DAY_DURATION, description="Leave duration in days")
    leave_session: Optional[str] = Field(None, description="Half-day session if applicable")
    employee_id: str
    name: str
    department: Optional[str] = None
    role: Optional[str] = None

    model_config = {"from_attributes": True}


class LeaveDisplayOut(BaseModel):
    """Schema for displaying user's own leave data without strict validation"""
    leave_id: int = Field(..., gt=0, description="Unique leave ID")
    company_id: int = Field(..., gt=0, description="Company this leave belongs to")
    user_id: int = Field(..., gt=0, description="User ID")
    start_date: date = Field(..., description="Leave start date")
    end_date: date = Field(..., description="Leave end date")
    reason: Optional[str] = Field(None, description="Leave reason")
    status: Optional[str] = Field("Pending", description="Leave status")
    leave_type: str = Field("annual", description="Type of leave")
    duration_days: float = Field(FULL_DAY_DURATION, description="Leave duration in days")
    leave_session: Optional[str] = Field(None, description="Half-day session if applicable")

    model_config = {"from_attributes": True}


class LeaveUpdate(BaseModel):
    start_date: Optional[date] = Field(None, description="New start date")
    end_date: Optional[date] = Field(None, description="New end date")
    reason: Optional[constr(min_length=10, max_length=500, strip_whitespace=True)] = Field(
        None, description="Updated reason"
    )
    leave_type: Optional[Literal['sick', 'casual', 'maternity', 'paternity', 'unpaid']] = Field(
        None, description="Updated leave type"
    )
    duration_days: Optional[float] = Field(None, description="1.0 or 0.5 for unpaid half day")
    leave_session: Optional[Literal['before_lunch', 'after_lunch']] = Field(
        None, description="Half-day session for unpaid leave"
    )

    @field_validator('duration_days')
    @classmethod
    def validate_duration_days(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v not in (FULL_DAY_DURATION, HALF_DAY_DURATION):
            raise ValueError('duration_days must be 1.0 or 0.5')
        return v

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v: Optional[date], info) -> Optional[date]:
        """Validate end date if provided"""
        if v is not None and 'start_date' in info.data and info.data['start_date'] is not None:
            if v < info.data['start_date']:
                raise ValueError('End date cannot be before start date')
        return v


class LeaveBalanceItem(BaseModel):
    leave_type: str = Field(..., description="Type of leave")
    allocated: int = Field(..., ge=0, description="Total allocated days")
    used: int = Field(..., ge=0, description="Days used")
    remaining: int = Field(..., ge=0, description="Days remaining")

    @field_validator('remaining')
    @classmethod
    def validate_remaining(cls, v: int, info) -> int:
        """Validate remaining is consistent with allocated and used"""
        if 'allocated' in info.data and 'used' in info.data:
            expected_remaining = info.data["allocated"] - info.data["used"]
            if v != expected_remaining:
                raise ValueError(
                    f'Remaining days ({v}) does not match allocated ({info.data["allocated"]}) '
                    f'- used ({info.data["used"]})'
                )
        return v


class LeaveBalanceResponse(BaseModel):
    balances: list[LeaveBalanceItem] = Field(..., description="List of leave balances by type")


class LeaveNotificationOut(BaseModel):
    notification_id: int = Field(..., gt=0, description="Notification ID")
    user_id: int = Field(..., gt=0, description="User ID")
    leave_id: Optional[int] = Field(None, gt=0, description="Leave ID")
    notification_type: str = Field(..., description="Notification type")
    title: constr(min_length=1, max_length=255) = Field(..., description="Notification title")
    message: constr(min_length=1, max_length=1000) = Field(..., description="Notification message")
    is_read: bool = Field(..., description="Read status")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}
