"""
Work From Home (WFH) Request Schemas
Pydantic models for request validation and response serialization.
"""
from pydantic import BaseModel, Field, field_validator, model_validator, constr
from datetime import date, datetime, timedelta
from typing import Optional, Literal


class WFHRequestCreate(BaseModel):
    """Schema for creating a new WFH request"""
    start_date: date = Field(..., description="WFH start date")
    end_date: date = Field(..., description="WFH end date")
    wfh_type: Literal['Full Day', 'Half Day'] = Field(default='Full Day', description="WFH type")
    reason: constr(min_length=10, max_length=500, strip_whitespace=True) = Field(
        ..., description="Reason for WFH request (10-500 characters)"
    )

    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v: date) -> date:
        """Validate start date"""
        if v < date(2000, 1, 1):
            raise ValueError('Start date cannot be before year 2000')
        # Allow backdated WFH requests up to 7 days for flexibility
        if v < date.today() - timedelta(days=7):
            raise ValueError('Cannot apply for WFH more than 7 days in the past')
        return v

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v: date, info) -> date:
        """Validate end date is not before start date"""
        if 'start_date' in info.data:
            start_date = info.data['start_date']
            if v < start_date:
                raise ValueError('End date cannot be before start date')
            # Maximum WFH duration: 30 days
            duration = (v - start_date).days + 1
            if duration > 30:
                raise ValueError('WFH duration cannot exceed 30 days per request')
        return v

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate reason is meaningful"""
        if not v or not v.strip():
            raise ValueError('WFH reason is required')
        v = v.strip()
        if len(v) < 10:
            raise ValueError('WFH reason must be at least 10 characters')
        if len(v) > 500:
            raise ValueError('WFH reason cannot exceed 500 characters')
        return v


class WFHRequestOut(BaseModel):
    """Schema for WFH request response"""
    wfh_id: int = Field(..., gt=0, description="WFH request ID")
    user_id: int = Field(..., gt=0, description="User ID")
    start_date: date = Field(..., description="WFH start date")
    end_date: date = Field(..., description="WFH end date")
    wfh_type: str = Field(default="Full Day", description="WFH type")
    reason: str = Field(..., description="Reason for WFH request")
    status: str = Field(default="Pending", description="Request status")
    approved_by: Optional[int] = Field(None, description="Approver user ID")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason")
    created_at: datetime = Field(..., description="Request submission timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    model_config = {"from_attributes": True}


class WFHRequestWithUserOut(WFHRequestOut):
    """Schema for WFH request with user details"""
    employee_id: Optional[str] = Field(None, description="Employee ID")
    name: str = Field(..., description="Employee name")
    department: Optional[str] = Field(None, description="Employee department")
    role: Optional[str] = Field(None, description="Employee role")
    approver_name: Optional[str] = Field(None, description="Approver name")

    model_config = {"from_attributes": True}


class WFHRequestApprove(BaseModel):
    """Schema for approving/rejecting a WFH request"""
    approved: bool = Field(..., description="True to approve, False to reject")
    rejection_reason: Optional[constr(min_length=10, max_length=500, strip_whitespace=True)] = Field(
        None, description="Reason for rejection (required if rejecting)"
    )
    @model_validator(mode='after')
    @classmethod
    def validate_rejection_reason(cls, model) -> object:
        """Enforce rejection_reason when approved is False (runs even if field omitted).
        Receives the model instance in 'after' mode, so access attributes directly."""
        approved = getattr(model, "approved", None)
        rejection_reason = getattr(model, "rejection_reason", None)

        if approved is False:
            if not rejection_reason or not str(rejection_reason).strip():
                raise ValueError('Rejection reason is required when rejecting a request')
            if len(str(rejection_reason).strip()) < 10:
                raise ValueError('Rejection reason must be at least 10 characters')
            model.rejection_reason = str(rejection_reason).strip()
        else:
            if rejection_reason:
                model.rejection_reason = str(rejection_reason).strip()

        return model


class WFHRequestUpdate(BaseModel):
    """Schema for updating a pending WFH request"""
    start_date: Optional[date] = Field(None, description="Updated start date")
    end_date: Optional[date] = Field(None, description="Updated end date")
    wfh_type: Optional[Literal['Full Day', 'Half Day']] = Field(None, description="Updated WFH type")
    reason: Optional[constr(min_length=10, max_length=500, strip_whitespace=True)] = Field(
        None, description="Updated reason"
    )

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v: Optional[date], info) -> Optional[date]:
        """Validate end date if provided"""
        if v is not None and 'start_date' in info.data and info.data['start_date'] is not None:
            if v < info.data['start_date']:
                raise ValueError('End date cannot be before start date')
        return v


class WFHRequestListResponse(BaseModel):
    """Schema for paginated list of WFH requests"""
    total: int = Field(..., description="Total number of requests")
    pending_count: int = Field(default=0, description="Number of pending requests")
    requests: list[WFHRequestWithUserOut] = Field(..., description="List of WFH requests")

