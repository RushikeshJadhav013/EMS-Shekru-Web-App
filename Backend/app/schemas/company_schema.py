from datetime import datetime
import re
from pydantic import BaseModel, EmailStr, validator

GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9A-Z]{1}Z[0-9]{1}$")


class CompanyBase(BaseModel):
    company_name: str
    # URL-safe identifier (used in tenant path routing). Generated from `company_name` if omitted.
    company_slug: str | None = None
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
        if not re.fullmatch(r"[6-9]\d{9}", value):
            raise ValueError("Contact number must be exactly 10 digits and start with 6, 7, 8, or 9")
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
        if not value:
            return None
        if not GSTIN_REGEX.fullmatch(value):
            raise ValueError(
                "Invalid GST number format. Expected 15 chars like '27ABCDE1234F1Z5'."
            )
        return value

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
        if not re.fullmatch(r"[6-9]\d{9}", value):
            raise ValueError("Contact number must be exactly 10 digits and start with 6, 7, 8, or 9")
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
        if not value:
            return None
        if not GSTIN_REGEX.fullmatch(value):
            raise ValueError(
                "Invalid GST number format. Expected 15 chars like '27ABCDE1234F1Z5'."
            )
        return value

    @validator("company_logo")
    def normalize_company_logo(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        return value or None


class CompanyStatusUpdate(BaseModel):
    status: bool


class CompanyOut(BaseModel):
    company_id: int
    company_name: str
    company_slug: str | None = None
    company_email: EmailStr
    contact_number: str
    address: str
    gst_no: str | None = None
    company_logo: str | None = None
    status: bool = True
    is_deleted: bool
    created_at: datetime | None = None
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    class Config:
        from_attributes = True


class AccessibleCompanyOut(BaseModel):
    """
    Lightweight company payload for tenant selection (admin multi-company).
    """

    company_id: int
    company_name: str
    company_slug: str | None = None
    company_logo: str | None = None
    status: bool = True

    class Config:
        from_attributes = True
