from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

class LeaveAllocationConfigBase(BaseModel):
    total_annual_leave: int = Field(..., ge=1, le=365, description="Total annual leave days (1-365). Note: In calculations, annual leave bucket = sick + casual")
    sick_leave_allocation: int = Field(..., ge=0, le=365, description="Sick leave allocation (0-365)")
    casual_leave_allocation: int = Field(..., ge=0, le=365, description="Casual leave allocation (0-365)")
    other_leave_allocation: int = Field(..., ge=0, le=365, description="Other leave allocation (0-365)")

    @field_validator('sick_leave_allocation', 'casual_leave_allocation', 'other_leave_allocation')
    @classmethod
    def validate_allocation(cls, v: int, info) -> int:
        """Validate that individual allocations are not negative"""
        if v < 0:
            raise ValueError('Leave allocation cannot be negative')
        return v

class LeaveAllocationConfigCreate(BaseModel):
    """Schema for creating leave allocation configuration (request body)."""

    # total_annual_leave: int = Field(..., ge=1, le=365, description="Derived as sick + casual")
    sick_leave_allocation: int = Field(..., ge=0, le=365, description="Sick leave allocation (0-365)")
    casual_leave_allocation: int = Field(..., ge=0, le=365, description="Casual leave allocation (0-365)")
    other_leave_allocation: int = Field(..., ge=0, le=365, description="Other leave allocation (0-365)")

    @field_validator('sick_leave_allocation', 'casual_leave_allocation', 'other_leave_allocation')
    @classmethod
    def validate_allocation(cls, v: int, info) -> int:
        """Validate that individual allocations are not negative."""
        if v < 0:
            raise ValueError('Leave allocation cannot be negative')
        return v

class LeaveAllocationConfigUpdate(BaseModel):
    """Schema for updating leave allocation configuration"""
    # total_annual_leave: Optional[int] = Field(None, ge=1, le=365)  # Derived as sick + casual
    sick_leave_allocation: Optional[int] = Field(None, ge=0, le=365)
    casual_leave_allocation: Optional[int] = Field(None, ge=0, le=365)
    other_leave_allocation: Optional[int] = Field(None, ge=0, le=365)

class LeaveAllocationConfigOut(LeaveAllocationConfigBase):
    """Schema for returning leave allocation configuration"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    updated_by: Optional[int] = None

    model_config = {"from_attributes": True}
