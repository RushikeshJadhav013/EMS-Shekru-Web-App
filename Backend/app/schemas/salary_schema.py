"""
Salary Schemas - Pydantic models for salary slip and increment letter
"""
from pydantic import BaseModel, Field, validator
import re
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class VariablePayType(str, Enum):
    """Variable pay configuration options"""
    NONE = "none"
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class EmployeeSalaryCTCCreate(BaseModel):
    """Schema for creating employee salary record from CTC"""
    user_id: int
    annual_ctc: float = Field(..., gt=0, description="Annual CTC amount (Package)")
    
    # Variable pay configuration
    variable_pay_type: VariablePayType = Field(default=VariablePayType.NONE)
    variable_pay_value: float = Field(default=0.0, ge=0, description="Percentage (0-100) or fixed amount")
    
    # Employer PF configuration (editable)
    employer_pf_percentage: float = Field(default=12.0, ge=0, le=100, description="Employer PF percentage (default 12%)")
    
    # Optional fields
    uan_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None
    working_days_per_month: int = Field(default=22, ge=1, le=31)
    payment_mode: str = Field(default="Bank Transfer")
    
    @validator('variable_pay_value')
    def validate_variable_pay_value(cls, v, values):
        if 'variable_pay_type' in values:
            vp_type = values['variable_pay_type']
            if vp_type == VariablePayType.PERCENTAGE and not (0 <= v <= 100):
                raise ValueError('Variable pay percentage must be between 0 and 100')
        return v

    @validator("uan_number", pre=True, always=False)
    def validate_uan_number_ctc_create(cls, v):
        if v is None:
            return v
        digits = re.sub(r'[^0-9]', '', str(v))
        if len(digits) != 12:
            raise ValueError("UAN must be exactly 12 digits")
        return digits

    @validator("ifsc_code", pre=True, always=False)
    def validate_ifsc_ctc_create(cls, v):
        if v is None:
            return v
        code = str(v).strip().upper()
        if len(code) != 11:
            raise ValueError("IFSC must be exactly 11 characters")
        # 4 letters, '0', then 6 alnum uppercase
        if not re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}', code):
            raise ValueError("Invalid IFSC format. Expected 4 letters, '0', then 6 alphanumeric characters (uppercase)")
        return code


class EmployeeSalaryCreate(BaseModel):
    """Schema for creating employee salary record (legacy - manual entry)"""
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
    uan_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None
    variable_pay: float = Field(default=0.0, ge=0)
    working_days_per_month: int = Field(default=22, ge=1, le=31)
    payment_mode: str = Field(default="Bank Transfer")

    @validator("uan_number", pre=True, always=False)
    def validate_uan_number_create(cls, v):
        if v is None:
            return v
        digits = re.sub(r'[^0-9]', '', str(v))
        if len(digits) != 12:
            raise ValueError("UAN must be exactly 12 digits")
        return digits

    @validator("ifsc_code", pre=True, always=False)
    def validate_ifsc_create(cls, v):
        if v is None:
            return v
        code = str(v).strip().upper()
        if len(code) != 11:
            raise ValueError("IFSC must be exactly 11 characters")
        if not re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}', code):
            raise ValueError("Invalid IFSC format. Expected 4 letters, '0', then 6 alphanumeric characters (uppercase)")
        return code


class EmployeeSalaryUpdate(BaseModel):
    """Schema for updating employee salary record - only non-fixed components"""
    # Only allow updating non-calculated fields
    uan_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None
    working_days_per_month: Optional[int] = Field(default=None, ge=1, le=31)
    payment_mode: Optional[str] = None
    
    # Variable pay can be updated
    variable_pay_type: Optional[VariablePayType] = None
    variable_pay_value: Optional[float] = Field(default=None, ge=0)
    
    # Other deductions (non-automatic)
    other_deduction_annual: Optional[float] = Field(default=None, ge=0)
    pf_annual: Optional[float] = Field(default=None, ge=0)

    @validator("uan_number", pre=True, always=False)
    def validate_uan_number_update(cls, v):
        if v is None:
            return v
        digits = re.sub(r'[^0-9]', '', str(v))
        if len(digits) != 12:
            raise ValueError("UAN must be exactly 12 digits")
        return digits

    @validator("ifsc_code", pre=True, always=False)
    def validate_ifsc_update(cls, v):
        if v is None:
            return v
        code = str(v).strip().upper()
        if len(code) != 11:
            raise ValueError("IFSC must be exactly 11 characters")
        if not re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}', code):
            raise ValueError("Invalid IFSC format. Expected 4 letters, '0', then 6 alphanumeric characters (uppercase)")
        return code


class EmployeeSalaryCTCUpdate(BaseModel):
    """Schema for updating salary by changing CTC"""
    annual_ctc: float = Field(..., gt=0, description="New Annual CTC amount (Package)")
    variable_pay_type: Optional[VariablePayType] = None
    variable_pay_value: Optional[float] = Field(default=None, ge=0)
    employer_pf_percentage: Optional[float] = Field(default=None, ge=0, le=100, description="Employer PF percentage (editable)")
    
    @validator('variable_pay_value')
    def validate_variable_pay_value(cls, v, values):
        if v is not None and 'variable_pay_type' in values:
            vp_type = values['variable_pay_type']
            if vp_type == VariablePayType.PERCENTAGE and not (0 <= v <= 100):
                raise ValueError('Variable pay percentage must be between 0 and 100')
        return v


    # Note: CTC update does not include uan_number by default. UAN validation is handled
    # by the create/update salary schemas where the field is present.


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


class SalaryCalculationPreview(BaseModel):
    """Schema for previewing salary calculation before saving"""
    annual_ctc: float
    total_gross_annual: float
    basic_annual: float
    hra_annual: float
    special_allowance_annual: float
    conveyance_annual: float
    medical_allowance_annual: float
    other_allowance_annual: float
    professional_tax_annual: float
    other_tax_annual: float
    employer_pf_annual: float
    variable_pay_annual: float
    
    # Monthly breakdown
    monthly_ctc: float
    monthly_gross: float
    monthly_basic: float
    monthly_hra: float
    monthly_special_allowance: float
    monthly_conveyance: float
    monthly_medical: float
    monthly_other: float
    monthly_professional_tax: float
    monthly_other_tax: float
    monthly_employer_pf: float
    monthly_variable_pay: float
    monthly_in_hand: float
    
    # Summary
    total_earnings_annual: float
    total_employee_deductions_annual: float
    total_employer_contributions_annual: float
    net_annual: float


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
