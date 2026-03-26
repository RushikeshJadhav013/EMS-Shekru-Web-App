from datetime import datetime
import re
from pydantic import BaseModel, EmailStr, validator


class CompanyBase(BaseModel):
    company_name: str
    company_email: EmailStr
    contact_number: str
    address: str
    gst_no: str | None = None
    company_logo: str | None = None
    status: bool = True

    @validator("company_name")
    def validate_company_name(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("Company name cannot be empty")
        return value

    @validator("company_email")
    def normalize_company_email(cls, v: str) -> str:
        return v.strip().lower()

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

    @validator("gst_no")
    def normalize_gst_no(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip().upper()
        return value or None

    @validator("company_logo")
    def normalize_company_logo(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        return value or None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    company_name: str | None = None
    company_email: EmailStr | None = None
    contact_number: str | None = None
    address: str | None = None
    gst_no: str | None = None
    company_logo: str | None = None
    status: bool | None = None

    @validator("company_name")
    def validate_company_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            raise ValueError("Company name cannot be empty")
        return value

    @validator("company_email")
    def normalize_company_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip().lower()

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

    @validator("gst_no")
    def normalize_gst_no(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip().upper()
        return value or None

    @validator("company_logo")
    def normalize_company_logo(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        return value or None


class CompanyStatusUpdate(BaseModel):
    status: bool


class CompanyOut(CompanyBase):
    company_id: int
    is_deleted: bool
    created_at: datetime | None = None
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    class Config:
        from_attributes = True
