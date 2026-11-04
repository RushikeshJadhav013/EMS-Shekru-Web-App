from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


def validate_non_empty(value):
    if value is None:
        raise ValueError("Field cannot be null.")

    if isinstance(value, str):
        value = value.strip()

        if not value:
            raise ValueError("Field cannot be empty or contain whitespace.")

    return value


class VendorCreate(BaseModel):
    vendor_name: str = Field(
        ..., min_length=1, max_length=150
    )
    contact_person: str = Field(
        ..., min_length=1, max_length=100
    )
    email: EmailStr
    phone: str = Field(
        ..., pattern=r"^[0-9]{10}$"
    )
    address: str = Field(
        ..., min_length=1, max_length=255
    )

    @field_validator(
        "vendor_name",
        "contact_person",
        "email",
        "phone",
        "address",
        mode="before",
    )
    @classmethod
    def reject_null_or_empty(cls, value):
        return validate_non_empty(value)


class VendorUpdate(BaseModel):
    vendor_name: str | None = Field(
        default=None, min_length=1, max_length=150
    )
    contact_person: str | None = Field(
        default=None, min_length=1, max_length=100
    )
    email: EmailStr | None = None
    phone: str | None = Field(
        default=None, pattern=r"^[0-9]{10}$"
    )
    address: str | None = Field(
        default=None, min_length=1, max_length=255
    )

    @field_validator(
        "vendor_name",
        "contact_person",
        "email",
        "phone",
        "address",
        mode="before",
    )
    @classmethod
    def reject_null_or_empty(cls, value):
        return validate_non_empty(value)


class VendorResponse(BaseModel):
    vendor_id: int
    company_id: int
    vendor_name: str
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None

    model_config = ConfigDict(from_attributes=True)