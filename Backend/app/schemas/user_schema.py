from pydantic import BaseModel, EmailStr, constr, validator, field_validator, Field
from typing import Optional, Literal, List
from datetime import datetime
import re
from app.enums import RoleEnum, GenderEnum
import re

class UserBase(BaseModel):
    name: constr(min_length=2, max_length=255, strip_whitespace=True) = Field(..., description="Full name (2-255 characters)")
    email: EmailStr = Field(..., description="Valid email address")
    department: Optional[constr(min_length=2, max_length=255, strip_whitespace=True)] = Field(None, description="Department name")
    designation: Optional[constr(min_length=2, max_length=255, strip_whitespace=True)] = Field(None, description="Job designation")
    phone: Optional[constr(min_length=10, max_length=20, strip_whitespace=True)] = Field(None, description="Phone number with country code")
    address: Optional[constr(max_length=500, strip_whitespace=True)] = Field(None, description="Full address")
    role: Optional[RoleEnum] = Field(RoleEnum.EMPLOYEE, description="User role")
    # Make gender mandatory in all user-related contexts
    gender: Literal['male', 'female', 'other'] = Field(..., description="Gender")
    
    @field_validator('gender', mode='before')
    @classmethod
    def normalize_gender(cls, v):
        """Normalize gender to lowercase when reading from database"""
        if v is None:
            raise ValueError('Gender is required')
        if isinstance(v, str):
            normalized = v.strip().lower()
            # Map common variations to lowercase
            if normalized in ['male', 'm']:
                return 'male'
            elif normalized in ['female', 'f']:
                return 'female'
            elif normalized in ['other', 'o']:
                return 'other'
            # If already lowercase and valid, return as is
            if normalized in ['male', 'female', 'other']:
                return normalized
            raise ValueError(f'Invalid gender value: {v}. Must be one of: male, female, other')
        return v
    
    resignation_date: Optional[datetime] = Field(None, description="Resignation date if applicable")
    joining_date: Optional[datetime] = Field(None, description="Date of joining (IST)")
    pan_card: Optional[constr(min_length=10, max_length=10, strip_whitespace=True)] = Field(None, description="PAN card number (10 characters)")
    aadhar_card: Optional[constr(min_length=14, max_length=14, strip_whitespace=True)] = Field(None, description="Aadhar card number (format: 1234-5678-9012)")
    shift_type: Optional[Literal['general', 'morning', 'afternoon', 'day', 'night', 'rotational', 'rotating']] = Field(None, description="Shift type")
    employee_type: Optional[str] = Field(None, description="Employment type")
    manager_id: Optional[int] = Field(None, description="Reporting manager user ID")

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
        # Require exactly 10 digits and starting with 6-9
        if not re.fullmatch(r'[6-9]\d{9}', digits):
            raise ValueError('Phone number must be exactly 10 digits and start with 6, 7, 8, or 9')
        return digits

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate address does not contain emojis"""
        if v is None:
            return v
        addr = v.strip()
        # Emoji detection: common emoji Unicode ranges
        emoji_pattern = re.compile(
            "[" 
            "\U0001F300-\U0001F5FF"
            "\U0001F600-\U0001F64F"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA70-\U0001FAFF"
            "\u2600-\u26FF\u2700-\u27BF"
            "]",
            flags=re.UNICODE,
        )
        if emoji_pattern.search(addr):
            raise ValueError("Address must not contain emojis")
        return addr

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

    # @field_validator('aadhar_card')
    # @classmethod
    # def validate_aadhar_card(cls, v: Optional[str]) -> Optional[str]:
    #     """Validate Aadhar card format: exactly 12 digits"""
    #     if v is None:
    #         return v
    #     v = re.sub(r'\D', '', v.strip())
    #     if not re.fullmatch(r'\d{12}', v):
    #         raise ValueError('Aadhar must be exactly 12 digits')
    #     return v

    @field_validator('aadhar_card')
    @classmethod
    def validate_aadhar_card(cls, v: Optional[str]) -> Optional[str]:
        """Validate Aadhar card format (1234-5678-9012)"""
        if v is None:
            return v
        v = v.strip()
        if not re.match(r'^\d{4}-\d{4}-\d{4}$', v):
            raise ValueError('Invalid Aadhar card format. Expected format: 1234-5678-9012')
        return v

    @validator("address", pre=True, always=False)
    def validate_admin_address(cls, v: Optional[str]) -> Optional[str]:
        """Admin address validator: disallow emojis and normalize"""
        if v is None:
            return v
        addr = v.strip()
        emoji_pattern = re.compile(
            "[" 
            "\U0001F300-\U0001F5FF"
            "\U0001F600-\U0001F64F"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA70-\U0001FAFF"
            "\u2600-\u26FF\u2700-\u27BF"
            "]",
            flags=re.UNICODE,
        )
        if emoji_pattern.search(addr):
            raise ValueError("Address must not contain emojis")
        return addr

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
    
    @field_validator('shift_type', mode='before')
    @classmethod
    def normalize_shift_type(cls, v: Optional[str]) -> Optional[str]:
        """Normalize shift_type to lowercase before Literal validation"""
        if v is None:
            return None
        if isinstance(v, str):
            return v.strip().lower()
        return v

class UserCreate(UserBase):
    employee_id: constr(min_length=1, max_length=50, strip_whitespace=True) = Field(..., description="Unique employee ID")
    profile_photo: Optional[str] = Field(None, description="Profile photo URL or path")
    # Tenant scope is set server-side based on admin assignment (or current_user scope).
    company_id: Optional[int] = Field(None, description="Company ID (set by server)")
    branch_id: Optional[int] = Field(None, description="Branch ID (set by server, optional)")

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

# class UserOut(UserBase):
#     user_id: int
#     employee_id: str
#     is_active: bool
#     profile_photo: Optional[str] = None
#     created_on: datetime
#     updated_on: Optional[datetime] = None
#     created_by: Optional[int] = None
#     updated_by: Optional[int] = None

#     model_config = {"from_attributes": True, "use_enum_values": True}
    
#     @field_validator('gender', mode='before')
#     @classmethod
#     def normalize_gender(cls, v):
#         """Normalize gender to lowercase when reading from database"""
#         if v is None:
#             return None
#         if isinstance(v, str):
#             normalized = v.strip().lower()
#             # Map common variations
#             if normalized in ['male', 'm']:
#                 return 'male'
#             elif normalized in ['female', 'f']:
#                 return 'female'
#             elif normalized in ['other', 'o']:
#                 return 'other'
#             return normalized
#         return v
    
#     @field_validator('aadhar_card', mode='before')
#     @classmethod
#     def normalize_aadhar_card(cls, v):
#         """Normalize Aadhar to raw 12 digits."""
#         if v is None:
#             return None
#         if isinstance(v, str):
#             digits_only = re.sub(r'\D', '', v.strip())
#             return digits_only or None
#         return v
    
#     @field_validator('shift_type', mode='before')
#     @classmethod
#     def normalize_shift_type(cls, v):
#         """Normalize shift_type to lowercase when reading from database"""
#         if v is None:
#             return None
#         if isinstance(v, str):
#             normalized = v.strip().lower()
#             # Map common variations
#             if normalized in ['morning', 'morn']:
#                 return 'morning'
#             elif normalized in ['afternoon', 'after']:
#                 return 'afternoon'
#             elif normalized in ['night', 'evening']:
#                 return 'night'
#             elif normalized in ['rotational', 'rotate', 'rotation']:
#                 return 'rotational'
#             elif normalized in ['general', 'gen']:
#                 return 'general'
#             return normalized
#         return v

class UserOut(UserBase):
    user_id: int
    employee_id: str
    is_active: bool
    profile_photo: Optional[str] = None
    created_at: datetime
    company_id: Optional[int] = None
    branch_id: Optional[int] = None

    model_config = {"from_attributes": True}


class UpdateRoleSchema(BaseModel):
    role: RoleEnum = Field(..., description="New role for the user")

class UpdateStatusSchema(BaseModel):
    is_active: bool = Field(..., description="Active status (true/false)")


class BulkUpdateStatusSchema(BaseModel):
    user_ids: List[int] = Field(..., min_length=1, description="List of user IDs to update")
    is_active: bool = Field(..., description="Active status (true/false)")


class AdminCreate(BaseModel):
    name: str
    email: EmailStr
    employee_id: str
    department: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    # Make gender mandatory for admin users as well
    gender: str
    shift_type: Optional[str] = None
    employee_type: Optional[str] = None
    pan_card: Optional[str] = None
    aadhar_card: Optional[str] = None
    joining_date: Optional[datetime] = None

    @validator("gender", pre=True, always=True)
    def validate_gender(cls, v):
        if v is None:
            raise ValueError('Gender is required')
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in ['male', 'm']:
                return 'male'
            elif normalized in ['female', 'f']:
                return 'female'
            elif normalized in ['other', 'o']:
                return 'other'
            if normalized in ['male', 'female', 'other']:
                return normalized
            raise ValueError(f'Invalid gender value: {v}. Must be one of: male, female, other')
        return v

    @validator("shift_type")
    def validate_shift_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = v.strip().lower()
        allowed = {'general', 'morning', 'afternoon', 'day', 'night', 'rotational', 'rotating'}
        if normalized not in allowed:
            raise ValueError(f"Shift type must be one of: {', '.join(sorted(allowed))}")
        return normalized
    
    @validator("employee_type")
    def validate_employee_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = v.strip()
        # Allow any non-empty string, or add allowed values if you want to enforce
        if not normalized:
            raise ValueError("Employee type cannot be empty if provided")
        return normalized
    
    @validator("name")
    def validate_name(cls, v: str) -> str:
        """Allow alphabetic characters with internal spaces; no leading/trailing spaces."""
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Name cannot be empty")
        if not re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+)*", trimmed):
            raise ValueError("Name must contain only letters and spaces, and not start with a space")
        return trimmed
    
    @validator("email")
    def validate_email(cls, v: str) -> str:
        """Normalize email to lowercase and strip whitespace."""
        if not v:
            raise ValueError("Email cannot be empty")
        normalized = v.strip().lower()
        return normalized

    @validator("address", pre=True, always=False)
    def validate_address_admincreate(cls, v: Optional[str]) -> Optional[str]:
        """Disallow emojis in admin-created addresses"""
        if v is None:
            return v
        addr = v.strip()
        emoji_pattern = re.compile(
            "[" 
            "\U0001F300-\U0001F5FF"
            "\U0001F600-\U0001F64F"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA70-\U0001FAFF"
            "\u2600-\u26FF\u2700-\u27BF"
            "]",
            flags=re.UNICODE,
        )
        if emoji_pattern.search(addr):
            raise ValueError("Address must not contain emojis")
        return addr
    
    @validator("phone")
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Require 10 digits starting with 5/6/7/8/9; allow missing."""
        if v is None:
            return None
        digits_only = v.strip()
        if not re.fullmatch(r"[6-9]\d{9}", digits_only):
            raise ValueError("Phone number must be 10 digits starting with 6, 7, 8, or 9")
        return digits_only
    
    @validator("pan_card")
    def validate_pan_card(cls, v: Optional[str]) -> Optional[str]:
        """
        PAN format: 10 characters, first 5 letters, next 4 digits, last letter.
        Returned value is uppercased. Empty is allowed.
        """
        if v is None:
            return None
        normalized = v.strip().upper()
        if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", normalized):
            raise ValueError("PAN must be 10 chars: 5 letters, 4 digits, last letter")
        return normalized

    @validator("aadhar_card")
    def validate_aadhar_card(cls, v: Optional[str]) -> Optional[str]:
        """Validate Aadhar card format (1234-5678-9012)"""
        if v is None:
            return None
        v = v.strip()
        if not re.match(r'^\d{4}-\d{4}-\d{4}$', v):
            raise ValueError('Invalid Aadhar card format. Expected format: 1234-5678-9012')
        return v


class AdminUpdate(BaseModel):
    name: Optional[str] = None
    shift_type: Optional[str] = None
    employee_type: Optional[str] = None

    @validator("shift_type")
    def validate_shift_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = v.strip().lower()
        allowed = {'general', 'morning', 'afternoon', 'day', 'night', 'rotational', 'rotating'}
        if normalized not in allowed:
            raise ValueError(f"Shift type must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @validator("employee_type")
    def validate_employee_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = v.strip()
        if not normalized:
            raise ValueError("Employee type cannot be empty if provided")
        return normalized

    @validator("name")
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Allow alphabetic characters with internal spaces; no leading/trailing spaces."""
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Name cannot be empty")
        if not re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+)*", trimmed):
            raise ValueError("Name must contain only letters and spaces, and not start with a space")
        return trimmed
    
    @validator("email")
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Normalize email to lowercase and strip whitespace."""
        if v is None:
            return None
        normalized = v.strip().lower()
        return normalized
    
    @validator("phone")
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Require 10 digits starting with 5/6/7/8/9; allow missing."""
        if v is None:
            return None
        digits_only = v.strip()
        if not re.fullmatch(r"[6-9]\d{9}", digits_only):
            raise ValueError("Phone number must be 10 digits starting with 6, 7, 8, or 9")
        return digits_only
    
    @validator("pan_card")
    def validate_pan_card(cls, v: Optional[str]) -> Optional[str]:
        """
        PAN format: 10 characters, first 5 letters, next 4 digits, last letter.
        Returned value is uppercased. Empty is allowed.
        """
        if v is None:
            return None
        normalized = v.strip().upper()
        if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", normalized):
            raise ValueError("PAN must be 10 chars: 5 letters, 4 digits, last letter")
        return normalized

    @validator("address", pre=True, always=False)
    def validate_address_adminupdate(cls, v: Optional[str]) -> Optional[str]:
        """Disallow emojis in admin-updated addresses"""
        if v is None:
            return v
        addr = v.strip()
        emoji_pattern = re.compile(
            "[" 
            "\U0001F300-\U0001F5FF"
            "\U0001F600-\U0001F64F"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA70-\U0001FAFF"
            "\u2600-\u26FF\u2700-\u27BF"
            "]",
            flags=re.UNICODE,
        )
        if emoji_pattern.search(addr):
            raise ValueError("Address must not contain emojis")
        return addr
    
    email: Optional[EmailStr] = None
    employee_id: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    # For updates, gender is optional.
    gender: Optional[str] = None
    shift_type: Optional[str] = None
    employee_type: Optional[str] = None
    pan_card: Optional[str] = None
    aadhar_card: Optional[str] = None
    is_active: Optional[bool] = None
    joining_date: Optional[datetime] = None

    @validator("gender", pre=True, always=True)
    def validate_gender(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in ['male', 'm']:
                return 'male'
            elif normalized in ['female', 'f']:
                return 'female'
            elif normalized in ['other', 'o']:
                return 'other'
            if normalized in ['male', 'female', 'other']:
                return normalized
            raise ValueError(f'Invalid gender value: {v}. Must be one of: male, female, other')
        return v
    
    @validator("aadhar_card")
    def validate_aadhar_card(cls, v: Optional[str]) -> Optional[str]:
        """Validate Aadhar card format (1234-5678-9012)"""
        if v is None:
            return None
        v = v.strip()
        if not re.match(r'^\d{4}-\d{4}-\d{4}$', v):
            raise ValueError('Invalid Aadhar card format. Expected format: 1234-5678-9012')
        return v
