from datetime import datetime
import re
from pydantic import BaseModel, EmailStr, validator


class CompanyBranchBase(BaseModel):
    company_id: int
    branch_name: str
    branch_email: EmailStr | None = None
    contact_number: str
    address: str
    # Branches are created as inactive by default because admins are assigned after
    # branch creation in the superadmin flow.
    status: bool = False

    @validator("branch_name")
    def validate_branch_name(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("Branch name cannot be empty")
        return value

    @validator("contact_number")
    def validate_contact_number(cls, v: str) -> str:
        value = v.strip()
        if not re.fullmatch(r"\d{10}", value):
            raise ValueError("Contact number must be exactly 10 digits")
        return value

    @validator("address")
    def validate_address(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("Address cannot be empty")
        return value


class CompanyBranchCreate(CompanyBranchBase):
    pass


class CompanyBranchUpdate(BaseModel):
    branch_name: str | None = None
    branch_email: EmailStr | None = None
    contact_number: str | None = None
    address: str | None = None
    status: bool | None = None

    @validator("branch_name")
    def validate_branch_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            raise ValueError("Branch name cannot be empty")
        return value

    @validator("contact_number")
    def validate_contact_number(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not re.fullmatch(r"\d{10}", value):
            raise ValueError("Contact number must be exactly 10 digits")
        return value

    @validator("address")
    def validate_address(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            raise ValueError("Address cannot be empty")
        return value


class CompanyBranchStatusUpdate(BaseModel):
    status: bool


class CompanyBranchOut(BaseModel):
    branch_id: int
    company_id: int
    branch_name: str
    branch_email: EmailStr | None = None
    contact_number: str
    address: str
    status: bool
    is_deleted: bool
    created_at: datetime | None = None
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    class Config:
        from_attributes = True

