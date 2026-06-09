from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.pin_utils import validate_pin_for_set, validate_pin_format


class LoginPinRequest(BaseModel):
    email: EmailStr
    pin: str = Field(..., min_length=4, max_length=4)

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, value: str) -> str:
        return validate_pin_format(value)


class SetPinRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=4)
    confirm_pin: str = Field(..., min_length=4, max_length=4)

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, value: str) -> str:
        return validate_pin_for_set(value)

    @field_validator("confirm_pin")
    @classmethod
    def pins_must_match(cls, value: str, info) -> str:
        pin = info.data.get("pin")
        if pin is not None and value != pin:
            raise ValueError("PIN and confirmation do not match")
        return validate_pin_format(value)


class ChangePinRequest(BaseModel):
    current_pin: str = Field(..., min_length=4, max_length=4)
    new_pin: str = Field(..., min_length=4, max_length=4)
    confirm_pin: str = Field(..., min_length=4, max_length=4)

    @field_validator("current_pin", "confirm_pin")
    @classmethod
    def validate_four_digit_pin(cls, value: str) -> str:
        return validate_pin_format(value)

    @field_validator("new_pin")
    @classmethod
    def validate_new_pin(cls, value: str) -> str:
        return validate_pin_for_set(value)

    @field_validator("confirm_pin")
    @classmethod
    def new_pins_must_match(cls, value: str, info) -> str:
        new_pin = info.data.get("new_pin")
        if new_pin is not None and value != new_pin:
            raise ValueError("New PIN and confirmation do not match")
        return value


class ResetPinRequest(BaseModel):
    email: EmailStr
    otp: int
    new_pin: str = Field(..., min_length=4, max_length=4)
    confirm_pin: str = Field(..., min_length=4, max_length=4)

    @field_validator("new_pin")
    @classmethod
    def validate_new_pin(cls, value: str) -> str:
        return validate_pin_for_set(value)

    @field_validator("confirm_pin")
    @classmethod
    def pins_must_match(cls, value: str, info) -> str:
        new_pin = info.data.get("new_pin")
        if new_pin is not None and value != new_pin:
            raise ValueError("PIN and confirmation do not match")
        return validate_pin_format(value)


class LoginOptionsResponse(BaseModel):
    email: str
    role: Optional[str] = None
    has_pin: bool
    pin_locked: bool
    pin_locked_until: Optional[datetime] = None
    available_methods: List[str]
    requires_pin_setup: bool = False
