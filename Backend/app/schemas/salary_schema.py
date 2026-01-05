"""
Salary Schemas - Pydantic models for salary slip and increment letter
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EmployeeSalaryCreate(BaseModel):
    """Schema for creating employee salary record"""
    user_id: int
    
    # Annual components
    basic_annual: float = Field(default=0.0, ge=0)
    hra_annual: float = Field(default=0.0, ge=0)
    special_allowance_annual: float = Field(default=0.0, ge=0)
    conveyance_annual: float = Field(default=0.0, ge=0)
    medical_allowance_annual: float = Field(default=0.0, ge=0)
    other_allowance_annual: float = Field(default=0.0, ge=0)
    
    # Deductions
    professional_tax_annual: float = Field(default=0.0, ge=0)
    other_deduction_annual: float = Field(default=0.0, ge=0)
    pf_annual: float = Field(default=0.0, ge=0)
    
    # Additional info
    pan_number: Optional[str] = None
    uan_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None
    variable_pay: float = Field(default=0.0, ge=0)
    working_days_per_month: int = Field(default=22, ge=1, le=31)
    payment_mode: str = Field(default="Bank Transfer")


class EmployeeSalaryUpdate(BaseModel):
    """Schema for updating employee salary record"""
    basic_annual: Optional[float] = Field(default=None, ge=0)
    hra_annual: Optional[float] = Field(default=None, ge=0)
    special_allowance_annual: Optional[float] = Field(default=None, ge=0)
    conveyance_annual: Optional[float] = Field(default=None, ge=0)
    medical_allowance_annual: Optional[float] = Field(default=None, ge=0)
    other_allowance_annual: Optional[float] = Field(default=None, ge=0)
    professional_tax_annual: Optional[float] = Field(default=None, ge=0)
    other_deduction_annual: Optional[float] = Field(default=None, ge=0)
    pf_annual: Optional[float] = Field(default=None, ge=0)
    pan_number: Optional[str] = None
    uan_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None
    variable_pay: Optional[float] = Field(default=None, ge=0)
    working_days_per_month: Optional[int] = Field(default=None, ge=1, le=31)
    payment_mode: Optional[str] = None


class EmployeeSalaryOut(BaseModel):
    """Schema for salary output"""
    id: int
    user_id: int
    basic_annual: float
    hra_annual: float
    special_allowance_annual: float
    conveyance_annual: float
    medical_allowance_annual: float
    other_allowance_annual: float
    professional_tax_annual: float
    other_deduction_annual: float
    pf_annual: float
    pan_number: Optional[str]
    uan_number: Optional[str]
    bank_name: Optional[str]
    bank_account: Optional[str]
    ifsc_code: Optional[str]
    variable_pay: float
    working_days_per_month: int
    payment_mode: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    total_earnings_annual: float
    total_deductions_annual: float
    ctc_annual: float
    monthly_ctc: float
    monthly_in_hand: float
    
    class Config:
        from_attributes = True


class SalaryIncrementCreate(BaseModel):
    """Schema for creating salary increment"""
    user_id: int
    previous_salary: float = Field(..., gt=0)
    increment_amount: float = Field(..., gt=0)
    new_salary: float = Field(..., gt=0)
    increment_percentage: Optional[float] = None
    effective_date: datetime
    reason: Optional[str] = None


class SalaryIncrementOut(BaseModel):
    """Schema for increment output"""
    id: int
    user_id: int
    previous_salary: float
    increment_amount: float
    new_salary: float
    increment_percentage: Optional[float]
    effective_date: datetime
    reason: Optional[str]
    approved_by: Optional[int]
    letter_sent: bool
    letter_sent_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class SalarySlipRequest(BaseModel):
    """Request schema for generating salary slip"""
    user_id: int
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000, le=2100)
    send_email: bool = Field(default=False)


class IncrementLetterRequest(BaseModel):
    """Request schema for generating increment letter"""
    increment_id: int
    send_email: bool = Field(default=False)


class SalaryAnnexureRequest(BaseModel):
    """Request schema for generating salary annexure/offer letter"""
    user_id: int
    send_email: bool = Field(default=False)


class EmailResponse(BaseModel):
    """Response schema for email operations"""
    success: bool
    message: str
    email_sent_to: Optional[str] = None
