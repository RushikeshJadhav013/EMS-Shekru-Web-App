"""
Salary Schemas - Pydantic models for salary slip and increment letter
"""
from pydantic import BaseModel, Field, validator
import re
from typing import Optional, Literal
from datetime import datetime
from enum import Enum
import re


def _validate_pf_no(v: Optional[str]) -> Optional[str]:
    """
    Validate Indian EPF PF number format: XX/XXX/XXXXXXX/XXX/XXXXXXX
    - 1st 2 chars: letters (Region)
    - 2nd 3 chars: letters (Office)
    - Rest all digits: XXXXXXX + XXX + XXXXXXX (7+3+7)
    """
    if v is None:
        return v
    s = str(v).strip()
    if not s:
        return None
    # XX/XXX/XXXXXXX/XXX/XXXXXXX - 2 letters, 3 letters, 7 digits, 3 digits, 7 digits
    if not re.fullmatch(r"[A-Z]{2}/[A-Z]{3}/[0-9]{7}/[0-9]{3}/[0-9]{7}", s, re.IGNORECASE):
        raise ValueError(
            "PF No must be XX/XXX/XXXXXXX/XXX/XXXXXXX (e.g. MH/BAN/0000064/000/0000123): "
            "2 letters, 3 letters, 7 digits, 3 digits, 7 digits"
        )
    return s.upper()


class VariablePayType(str, Enum):
    """Variable pay configuration options"""
    NONE = "none"
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class EmployeeSalaryCTCCreate(BaseModel):
    """Schema for creating employee salary record from CTC"""
    user_id: int
    # Package CTC is now required and used for all calculations (replaces annual_ctc)
    package_ctc_annual: float = Field(..., gt=0, description="Offered package CTC for display (required)")
    
    # Variable pay configuration
    variable_pay_type: VariablePayType = Field(default=VariablePayType.NONE)
    variable_pay_value: float = Field(default=0.0, ge=0, description="Percentage (0-100) or fixed amount")
    
    # Employer PF configuration (editable)
    employer_pf_percentage: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Employer PF percentage (optional). Defaults to null; provide value manually when needed."
    )
    pf_annual: Optional[float] = Field(
        default=None,
        ge=0,
        description="PF annual amount (optional). Provide either this OR employer_pf_percentage, not both."
    )
    
    # Optional fields
    uan_number: Optional[str] = None
    pf_no: Optional[str] = None
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

    @validator("pf_annual", always=True)
    def validate_pf_input_mode_ctc_create(cls, v, values):
        pct = values.get("employer_pf_percentage")
        if pct is not None and v is not None:
            raise ValueError(
                "Provide either employer_pf_percentage or pf_annual, not both."
            )
        return v

    @validator("uan_number", pre=True, always=False)
    def validate_uan_number_ctc_create(cls, v):
        if v is None:
            return v
        digits = re.sub(r'[^0-9]', '', str(v))
        if len(digits) != 12:
            raise ValueError("UAN must be exactly 12 digits")
        return digits

    @validator("pf_no", pre=True, always=False)
    def validate_pf_no_ctc_create(cls, v):
        return _validate_pf_no(v)

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
    pf_annual: Optional[float] = Field(default=None, ge=0)
    employer_pf_percentage: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Optional PF percentage. Provide either this OR pf_annual, not both."
    )
    
    # Additional info
    uan_number: Optional[str] = None
    pf_no: Optional[str] = None
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

    @validator("pf_no", pre=True, always=False)
    def validate_pf_no_create(cls, v):
        return _validate_pf_no(v)

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

    @validator("pf_annual", always=True)
    def validate_pf_input_mode_create(cls, v, values):
        pct = values.get("employer_pf_percentage")
        if pct is not None and v is not None:
            raise ValueError("Provide either employer_pf_percentage or pf_annual, not both.")
        return v


class EmployeeSalaryUpdate(BaseModel):
    """Schema for updating employee salary record - only non-fixed components"""
    # Only allow updating non-calculated fields
    uan_number: Optional[str] = None
    pf_no: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None
    working_days_per_month: Optional[int] = Field(default=22, ge=1, le=31)
    payment_mode: Optional[str] = Field(default="Bank Transfer")
    
    # Variable pay can be updated
    variable_pay_type: Optional[VariablePayType] = None
    variable_pay_value: Optional[float] = Field(default=None, ge=0)
    
    # Other deductions (non-automatic)
    # other_deduction_annual: Optional[float] = Field(default=None, ge=0)
    pf_annual: Optional[float] = Field(default=None, ge=0)
    employer_pf_percentage: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Optional PF percentage. Provide either this OR pf_annual, not both."
    )

    @validator("uan_number", pre=True, always=False)
    def validate_uan_number_update(cls, v):
        if v is None:
            return v
        digits = re.sub(r'[^0-9]', '', str(v))
        if len(digits) != 12:
            raise ValueError("UAN must be exactly 12 digits")
        return digits

    @validator("pf_no", pre=True, always=False)
    def validate_pf_no_update(cls, v):
        return _validate_pf_no(v)

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

    @validator("pf_annual", always=True)
    def validate_pf_input_mode_update(cls, v, values):
        pct = values.get("employer_pf_percentage")
        if pct is not None and v is not None:
            raise ValueError("Provide either employer_pf_percentage or pf_annual, not both.")
        return v


class EmployeeSalaryManualFullUpdate(BaseModel):
    """Schema for manual full-edit salary update (direct component editing)."""
    basic_annual: Optional[float] = Field(default=None, ge=0)
    hra_annual: Optional[float] = Field(default=None, ge=0)
    special_allowance_annual: Optional[float] = Field(default=None, ge=0)
    conveyance_annual: Optional[float] = Field(default=None, ge=0)
    medical_allowance_annual: Optional[float] = Field(default=None, ge=0)
    other_allowance_annual: Optional[float] = Field(default=None, ge=0)
    professional_tax_annual: Optional[float] = Field(default=None, ge=0)
    other_deduction_annual: Optional[float] = Field(default=None, ge=0)
    pf_annual: Optional[float] = Field(default=None, ge=0)
    employer_pf_percentage: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Optional PF percentage. Provide either this OR pf_annual, not both."
    )
    variable_pay: Optional[float] = Field(default=None, ge=0)
    uan_number: Optional[str] = None
    pf_no: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None
    working_days_per_month: Optional[int] = Field(default=22, ge=1, le=31)
    payment_mode: Optional[str] = Field(default="Bank Transfer")

    @validator("uan_number", pre=True, always=False)
    def validate_uan_number_manual_full_update(cls, v):
        if v is None:
            return v
        digits = re.sub(r'[^0-9]', '', str(v))
        if len(digits) != 12:
            raise ValueError("UAN must be exactly 12 digits")
        return digits

    @validator("pf_no", pre=True, always=False)
    def validate_pf_no_manual_full_update(cls, v):
        return _validate_pf_no(v)

    @validator("ifsc_code", pre=True, always=False)
    def validate_ifsc_manual_full_update(cls, v):
        if v is None:
            return v
        code = str(v).strip().upper()
        if len(code) != 11:
            raise ValueError("IFSC must be exactly 11 characters")
        if not re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}', code):
            raise ValueError("Invalid IFSC format. Expected 4 letters, '0', then 6 alphanumeric characters (uppercase)")
        return code

    @validator("pf_annual", always=True)
    def validate_pf_input_mode_manual_full_update(cls, v, values):
        pct = values.get("employer_pf_percentage")
        if pct is not None and v is not None:
            raise ValueError("Provide either employer_pf_percentage or pf_annual, not both.")
        return v


class EmployeeSalaryStatusUpdate(BaseModel):
    """Schema for updating salary active status"""
    is_active: bool


class EmployeeSalaryCTCUpdate(BaseModel):
    """Schema for updating salary by changing CTC"""
    # New package CTC to replace annual_ctc usage
    package_ctc_annual: float = Field(..., gt=0, description="New package CTC amount (Package)")
    variable_pay_type: Optional[VariablePayType] = None
    variable_pay_value: Optional[float] = Field(default=None, ge=0)
    employer_pf_percentage: Optional[float] = Field(default=None, ge=0, le=100, description="Employer PF percentage (editable)")
    pf_annual: Optional[float] = Field(
        default=None,
        ge=0,
        description="PF annual amount (optional). Provide either this OR employer_pf_percentage, not both."
    )
    
    @validator('variable_pay_value')
    def validate_variable_pay_value(cls, v, values):
        if v is not None and 'variable_pay_type' in values:
            vp_type = values['variable_pay_type']
            if vp_type == VariablePayType.PERCENTAGE and not (0 <= v <= 100):
                raise ValueError('Variable pay percentage must be between 0 and 100')
        return v

    @validator("pf_annual", always=True)
    def validate_pf_input_mode_ctc_update(cls, v, values):
        pct = values.get("employer_pf_percentage")
        if pct is not None and v is not None:
            raise ValueError(
                "Provide either employer_pf_percentage or pf_annual, not both."
            )
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
    pf_annual: Optional[float]
    pan_number: Optional[str]
    uan_number: Optional[str]
    pf_no: Optional[str]
    bank_name: Optional[str]
    bank_account: Optional[str]
    ifsc_code: Optional[str]
    variable_pay: float
    working_days_per_month: int
    payment_mode: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Computed fields
    total_earnings_annual: float
    total_deductions_annual: float
    package_ctc_annual: float  # Offered package CTC (for display) - required replacement for ctc_annual
    display_ctc_annual: float  # CTC to display (package if set, else calculated)
    monthly_ctc: float  # Calculated monthly CTC
    display_monthly_ctc: float  # Monthly CTC to display
    monthly_in_hand: float
    
    class Config:
        from_attributes = True


class SalaryCalculationPreview(BaseModel):
    """Schema for previewing salary calculation before saving"""
    package_ctc_annual: float
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
    """Schema for creating salary increment with CTC calculation"""
    user_id: int
    
    # Option 1: Provide increment amount (annual CTC increment)
    increment_ctc_annual: Optional[float] = Field(None, gt=0, description="Annual CTC increment amount")
    
    # Option 2: Provide increment percentage
    increment_percentage: Optional[float] = Field(None, gt=0, le=100, description="Increment percentage")
    
    # Required fields
    effective_date: datetime
    reason: Optional[str] = None
    
    # Optional: override variable pay configuration when applying increment
    # If not provided, existing variable pay settings on the salary record are reused.
    variable_pay_type: Optional[VariablePayType] = Field(
        default=None,
        description="Variable pay type to apply along with increment (none/percentage/fixed). "
                    "If omitted, existing variable pay configuration is kept."
    )
    variable_pay_value: Optional[float] = Field(
        default=None,
        ge=0,
        description="Variable pay percentage (0-100) or fixed amount, depending on variable_pay_type."
    )
    
    @validator('increment_percentage')
    def validate_increment_input(cls, v, values):
        """Ensure either increment_ctc_annual OR increment_percentage is provided"""
        increment_amount = values.get('increment_ctc_annual')
        if v is None and increment_amount is None:
            raise ValueError('Either increment_ctc_annual or increment_percentage must be provided')
        if v is not None and increment_amount is not None:
            raise ValueError('Provide either increment_ctc_annual OR increment_percentage, not both')
        return v


class SalaryIncrementOut(BaseModel):
    """Schema for increment output"""
    id: int
    user_id: int
    
    # Variable pay configuration that was applied (if any)
    # variable_pay_type: Optional[VariablePayType] = None  # commented out as per requirement
    variable_pay_value: Optional[float] = None
    
    # Legacy monthly salary fields (for backward compatibility)
    previous_salary: float
    increment_amount: float
    new_salary: float
    
    # CTC fields (Annual)
    previous_ctc_annual: Optional[float]
    increment_ctc_annual: Optional[float]
    new_ctc_annual: Optional[float]
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


class SalaryNotificationCreate(BaseModel):
    """Schema for creating a salary notification"""
    user_id: int
    notification_type: str
    title: str
    message: str


class SalaryNotificationOut(BaseModel):
    """Schema for salary notification output"""
    notification_id: int
    user_id: int
    notification_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
