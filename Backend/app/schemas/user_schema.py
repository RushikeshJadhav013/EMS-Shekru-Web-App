from pydantic import BaseModel, EmailStr, constr, field_validator, Field
from typing import Optional, Literal
from datetime import datetime
from app.enums import RoleEnum
import re

def _normalize_literal(value: Optional[str], *, mapping: dict[str, str], field_name: str) -> Optional[str]:
    """Normalize literal inputs (case/alias insensitive)."""
    if value is None:
        return value
    normalized = str(value).strip().lower()
    if normalized not in mapping:
        raise ValueError(f"Invalid {field_name}. Supported values: {', '.join(sorted(set(mapping.values())))}")
    return mapping[normalized]


class UserBase(BaseModel):
    name: constr(min_length=2, max_length=255, strip_whitespace=True) = Field(..., description="Full name (2-255 characters)")
    email: EmailStr = Field(..., description="Valid email address")
    department: Optional[constr(min_length=2, max_length=255, strip_whitespace=True)] = Field(None, description="Department name")
    designation: Optional[constr(min_length=2, max_length=255, strip_whitespace=True)] = Field(None, description="Job designation")
    phone: Optional[constr(min_length=10, max_length=20, strip_whitespace=True)] = Field(None, description="Phone number with country code")
    address: Optional[constr(max_length=500, strip_whitespace=True)] = Field(None, description="Full address")
    role: Optional[RoleEnum] = Field(RoleEnum.EMPLOYEE, description="User role")
    gender: Optional[Literal['male', 'female', 'other']] = Field(None, description="Gender")
    resignation_date: Optional[datetime] = Field(None, description="Resignation date if applicable")
    pan_card: Optional[constr(min_length=10, max_length=10, strip_whitespace=True)] = Field(None, description="PAN card number (10 characters)")
    aadhar_card: Optional[constr(min_length=14, max_length=14, strip_whitespace=True)] = Field(None, description="Aadhar card number (format: 1234-5678-9012)")
    shift_type: Optional[Literal['general', 'morning', 'afternoon', 'night', 'rotational']] = Field(None, description="Shift type")
    employee_type: Optional[Literal['contract', 'permanent']] = Field(None, description="Employment type")

    @field_validator('department', 'designation', 'phone', 'address', 'pan_card', 'aadhar_card', mode='before')
    @classmethod
    def strip_empty_optional_fields(cls, v: Optional[str]) -> Optional[str]:
        """
        Normalize blank strings from the database or forms to None for optional fields.

        This prevents Pydantic from treating "" as a real value and failing
        min_length validations on fields like designation/phone when legacy
        rows store empty strings instead of NULL.
        """
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name contains only letters and spaces"""
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        if not re.match(r'^[a-zA-Z\s]+$', v):
            raise ValueError('Name must contain only letters and spaces')
        return v.strip()

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number format"""
        if v is None:
            return v
        # Remove all non-digit characters for validation
        digits = re.sub(r'[^0-9]', '', v)
        if len(digits) < 10:
            raise ValueError('Phone number must have at least 10 digits')
        if len(digits) > 15:
            raise ValueError('Phone number cannot exceed 15 digits')
        return v.strip()

    @field_validator('gender', mode='before')
    @classmethod
    def normalize_gender(cls, v: Optional[str]) -> Optional[str]:
        """Allow case-insensitive gender input."""
        mapping = {
            'male': 'male',
            'm': 'male',
            'female': 'female',
            'f': 'female',
            'other': 'other',
            'o': 'other'
        }
        return _normalize_literal(v, mapping=mapping, field_name='gender')

    @field_validator('shift_type', mode='before')
    @classmethod
    def normalize_shift(cls, v: Optional[str]) -> Optional[str]:
        """Support common aliases for shift types."""
        mapping = {
            'general': 'general',
            'day': 'general',
            'day shift': 'general',
            'morning': 'morning',
            'afternoon': 'afternoon',
            'evening': 'afternoon',
            'night': 'night',
            'night shift': 'night',
            'rotational': 'rotational',
            'rotation': 'rotational'
        }
        return _normalize_literal(v, mapping=mapping, field_name='shift type')

    @field_validator('employee_type', mode='before')
    @classmethod
    def normalize_employee_type(cls, v: Optional[str]) -> Optional[str]:
        """Normalize employment type."""
        mapping = {
            'contract': 'contract',
            'contractual': 'contract',
            'permanent': 'permanent',
            'fulltime': 'permanent',
            'full-time': 'permanent',
            # Handle legacy/variant value stored in some databases
            'full time': 'permanent',
        }
        return _normalize_literal(v, mapping=mapping, field_name='employee type')

    @field_validator('pan_card')
    @classmethod
    def validate_pan_card(cls, v: Optional[str]) -> Optional[str]:
        """Validate PAN card format (ABCDE1234F)"""
        if v is None:
            return v
        v = v.strip().upper()
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', v):
            raise ValueError('Invalid PAN card format. Expected format: ABCDE1234F')
        return v

    @field_validator('aadhar_card', mode='before')
    @classmethod
    def validate_aadhar_card(cls, v: Optional[str]) -> Optional[str]:
        """Validate Aadhar card format (1234-5678-9012) while allowing raw digits."""
        if v is None:
            return v
        digits = re.sub(r'\D', '', v)
        if len(digits) != 12:
            raise ValueError('Invalid Aadhar card format. Expected 12 digits (e.g., 1234-5678-9012)')
        return f"{digits[0:4]}-{digits[4:8]}-{digits[8:12]}"

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Additional email validation"""
        if not v or not v.strip():
            raise ValueError('Email cannot be empty')
        v = v.strip().lower()
        # Check for common invalid patterns
        if '..' in v or v.startswith('.') or '@.' in v or '.@' in v:
            raise ValueError('Invalid email format')
        return v

    @field_validator('resignation_date')
    @classmethod
    def validate_resignation_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate resignation date is not in the future beyond reasonable limits"""
        if v is None:
            return v
        if v < datetime(1900, 1, 1):
            raise ValueError('Resignation date cannot be before 1900')
        return v

class UserCreate(UserBase):
    employee_id: constr(min_length=1, max_length=50, strip_whitespace=True) = Field(..., description="Unique employee ID")
    profile_photo: Optional[str] = Field(None, description="Profile photo URL or path")

    @field_validator('employee_id')
    @classmethod
    def validate_employee_id(cls, v: str) -> str:
        """Validate employee ID format"""
        if not v or not v.strip():
            raise ValueError('Employee ID cannot be empty')
        v = v.strip()
        # Remove spaces from employee ID
        if ' ' in v:
            raise ValueError('Employee ID cannot contain spaces')
        return v

class UserOut(UserBase):
    user_id: int
    employee_id: str
    is_active: bool
    profile_photo: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class UpdateRoleSchema(BaseModel):
    role: RoleEnum = Field(..., description="New role for the user")

class UpdateStatusSchema(BaseModel):
    is_active: bool = Field(..., description="Active status (true/false)")
