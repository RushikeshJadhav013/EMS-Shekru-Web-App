
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class VendorCreate(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=150)
    contact_person: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=255)


class VendorUpdate(BaseModel):
    vendor_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    contact_person: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=255)


class VendorResponse(BaseModel):
    vendor_id: int
    company_id: int
    vendor_name: str
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None

    model_config = ConfigDict(from_attributes=True)
