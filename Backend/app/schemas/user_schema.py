from pydantic import BaseModel, EmailStr, constr, validator
from typing import Optional
from datetime import datetime
import re
from app.enums import RoleEnum

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
    department: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role: Optional[RoleEnum] = RoleEnum.EMPLOYEE
    gender: Optional[str] = None
    resignation_date: Optional[datetime] = None
    pan_card: Optional[str] = None
    aadhar_card: Optional[str] = None
    shift_type: Optional[str] = None
    employee_type: Optional[str] = None  # ✅ Added: contract or permanent

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

    model_config = {"from_attributes": True}

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
    gender: Optional[str] = None
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
    email: Optional[EmailStr] = None
    employee_id: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gender: Optional[str] = None
    shift_type: Optional[str] = None
    employee_type: Optional[str] = None
    pan_card: Optional[str] = None
    aadhar_card: Optional[str] = None
    is_active: Optional[bool] = None
