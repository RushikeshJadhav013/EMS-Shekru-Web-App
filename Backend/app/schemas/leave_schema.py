from pydantic import BaseModel, Field, field_validator, constr
from datetime import date, datetime, timedelta
from typing import Optional, Literal

class LeaveBase(BaseModel):
    start_date: date = Field(..., description="Leave start date")
    end_date: date = Field(..., description="Leave end date")
    reason: Optional[constr(min_length=10, max_length=500, strip_whitespace=True)] = Field(None, description="Leave reason (10-500 characters)")
    status: Optional[Literal['Pending', 'Approved', 'Rejected']] = Field("Pending", description="Leave status")
    leave_type: Literal['annual', 'sick', 'casual', 'maternity', 'paternity', 'work_from_home'] = Field("annual", description="Type of leave")

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v: date, info) -> date:
        """Validate end date is not before start date"""
        if 'start_date' in info.data:
            start_date = info.data['start_date']
            if v < start_date:
                raise ValueError('End date cannot be before start date')
            # Validate reasonable leave duration (max 365 days)
            duration = (v - start_date).days + 1
            if duration > 365:
                raise ValueError('Leave duration cannot exceed 365 days')
        return v

    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v: date) -> date:
        """Validate start date is not too far in the past"""
        if v < date(2000, 1, 1):
            raise ValueError('Start date cannot be before year 2000')
        # Allow backdated leaves up to 30 days
        if v < date.today() - timedelta(days=30):
            raise ValueError('Cannot apply for leave more than 30 days in the past')
        return v

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
    employee_id: constr(min_length=1, max_length=50, strip_whitespace=True) = Field(..., description="Employee ID")

    @field_validator('employee_id')
    @classmethod
    def validate_employee_id(cls, v: str) -> str:
        """Validate employee ID is not empty"""
        if not v or not v.strip():
            raise ValueError('Employee ID cannot be empty')
        return v.strip()


class LeaveOut(LeaveBase):
    leave_id: int = Field(..., gt=0, description="Unique leave ID")
    user_id: int = Field(..., gt=0, description="User ID")

    model_config = {"from_attributes": True}


class LeaveWithUserOut(LeaveOut):
    employee_id: str
    name: constr(min_length=1, max_length=255)
    department: Optional[str] = None
    role: Optional[str] = None


class LeaveUpdate(BaseModel):
    start_date: Optional[date] = Field(None, description="New start date")
    end_date: Optional[date] = Field(None, description="New end date")
    reason: Optional[constr(min_length=10, max_length=500, strip_whitespace=True)] = Field(None, description="Updated reason")
    leave_type: Optional[Literal['annual', 'sick', 'casual', 'maternity', 'paternity', 'work_from_home']] = Field(None, description="Updated leave type")

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
            expected_remaining = info.data['allocated'] - info.data['used']
            if v != expected_remaining:
                raise ValueError(f'Remaining days ({v}) does not match allocated ({info.data["allocated"]}) - used ({info.data["used"]})')
        return v


class LeaveBalanceResponse(BaseModel):
    balances: list[LeaveBalanceItem] = Field(..., description="List of leave balances by type")


class LeaveNotificationOut(BaseModel):
    notification_id: int = Field(..., gt=0, description="Notification ID")
    user_id: int = Field(..., gt=0, description="User ID")
    leave_id: int = Field(..., gt=0, description="Leave ID")
    notification_type: str = Field(..., description="Notification type")
    title: constr(min_length=1, max_length=255) = Field(..., description="Notification title")
    message: constr(min_length=1, max_length=1000) = Field(..., description="Notification message")
    is_read: bool = Field(..., description="Read status")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}