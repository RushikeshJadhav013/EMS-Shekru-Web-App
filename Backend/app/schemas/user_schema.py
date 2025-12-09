from pydantic import BaseModel, EmailStr, constr, validator
from typing import Optional
from datetime import datetime
import re
from app.enums import RoleEnum, GenderEnum

class UserBase(BaseModel):
    name: str
    email: EmailStr
    
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
    
    department: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role: Optional[RoleEnum] = RoleEnum.EMPLOYEE
    gender: GenderEnum | None = None
    resignation_date: Optional[datetime] = None
    pan_card: Optional[str] = None
    aadhar_card: Optional[str] = None
    shift_type: Optional[str] = None
    employee_type: Optional[str] = None  # ✅ Added: contract or permanent

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
        """Aadhar must be exactly 12 digits; allow missing."""
        if v is None:
            return None
        digits_only = v.strip()
        if not re.fullmatch(r"\d{12}", digits_only):
            raise ValueError("Aadhar must be exactly 12 digits")
        return digits_only

    @validator("phone")
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Require 10 digits starting with 6/7/8/9; allow missing."""
        if v is None:
            return None
        digits_only = v.strip()
        if not re.fullmatch(r"[6789]\d{9}", digits_only):
            raise ValueError("Phone number must be 10 digits starting with 6, 7, 8, or 9")
        return digits_only

class UserCreate(UserBase):
    employee_id: str
    profile_photo: Optional[str] = None

class UserOut(UserBase):
    user_id: int
    employee_id: str
    is_active: bool
    profile_photo: Optional[str] = None
    created_on: datetime
    updated_on: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

    model_config = {"from_attributes": True, "use_enum_values": True}

class UpdateRoleSchema(BaseModel):
    role: RoleEnum

class UpdateStatusSchema(BaseModel):
    is_active: bool


class AdminCreate(BaseModel):
    name: str
    email: EmailStr
    employee_id: str
    department: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gender: GenderEnum | None = None
    shift_type: Optional[str] = None
    employee_type: Optional[str] = None
    pan_card: Optional[str] = None
    aadhar_card: Optional[str] = None
    
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
    
    @validator("phone")
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Require 10 digits starting with 6/7/8/9; allow missing."""
        if v is None:
            return None
        digits_only = v.strip()
        if not re.fullmatch(r"[6789]\d{9}", digits_only):
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
        """Aadhar must be exactly 12 digits; allow missing."""
        if v is None:
            return None
        digits_only = v.strip()
        if not re.fullmatch(r"\d{12}", digits_only):
            raise ValueError("Aadhar must be exactly 12 digits")
        return digits_only


class AdminUpdate(BaseModel):
    name: Optional[str] = None
    
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
        """Require 10 digits starting with 6/7/8/9; allow missing."""
        if v is None:
            return None
        digits_only = v.strip()
        if not re.fullmatch(r"[6789]\d{9}", digits_only):
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
    
    email: Optional[EmailStr] = None
    employee_id: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gender: GenderEnum | None = None
    shift_type: Optional[str] = None
    employee_type: Optional[str] = None
    pan_card: Optional[str] = None
    aadhar_card: Optional[str] = None
    is_active: Optional[bool] = None
    
    @validator("aadhar_card")
    def validate_aadhar_card(cls, v: Optional[str]) -> Optional[str]:
        """Aadhar must be exactly 12 digits; allow missing."""
        if v is None:
            return None
        digits_only = v.strip()
        if not re.fullmatch(r"\d{12}", digits_only):
            raise ValueError("Aadhar must be exactly 12 digits")
        return digits_only
