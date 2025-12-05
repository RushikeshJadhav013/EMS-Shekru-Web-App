from datetime import datetime
import re
from pydantic import BaseModel, EmailStr, validator

class SuperAdminBase(BaseModel):
    name: str
    email: EmailStr
    contact_no: str
    gender: str | None = None

    @validator("name")
    def validate_name(cls, v: str) -> str:
        """Allow alphabetic characters with internal spaces; no leading/trailing spaces."""
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Name cannot be empty")
        if not re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+)*", trimmed):
            raise ValueError("Name must contain only letters and spaces, and not start with a space")
        return trimmed

class SuperAdminCreate(SuperAdminBase):
    pass

class SuperAdminUpdate(SuperAdminBase):
    name: str | None = None
    email: EmailStr | None = None
    contact_no: str | None = None
    gender: str | None = None


class SuperAdminOut(SuperAdminBase):
    super_admin_id: int
    is_active: bool
    created_on: datetime | None = None
    updated_on: datetime | None = None
    created_by: int | None = None
    updated_by: int | None = None

    class Config:
        from_attributes = True
