
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.enums import ExpenseCategoryEnum


class ExpenseBase(BaseModel):
    category: ExpenseCategoryEnum
    sub_category: str = Field(..., min_length=1, max_length=100)
    expense_date: datetime
    amount: Decimal = Field(..., gt=0)

    description: str | None = None

    vendor_id: int = Field(..., gt=0)
    invoice_number: str | None = Field(default=None, max_length=100)
    invoice_date: date | None = None
    gst_number: str | None = Field(default=None, max_length=30)
    gst_amount: Decimal | None = Field(default=None, ge=0)

    cost_center: str | None = Field(default=None, max_length=100)
    project_name: str | None = Field(default=None, max_length=150)
    client_name: str | None = Field(default=None, max_length=150)

    @field_validator(
        "sub_category",
        "description",
        "invoice_number",
        "gst_number",
        "cost_center",
        "project_name",
        "client_name",
        mode="before",
    )
    @classmethod
    def validate_text_fields(cls, value: Any) -> Any:
        if value is None:
            return value

        if not isinstance(value, str):
            raise ValueError("Value must be a string.")

        value = value.strip()

        if not value:
            raise ValueError("Empty or whitespace-only values are not allowed.")

        return value

    @field_validator("expense_date")
    @classmethod
    def validate_expense_date(cls, value: datetime) -> datetime:
        if value.date() >= date.today():
            raise ValueError("Expense date must be earlier than today.")

        return value


class ExpenseCreate(ExpenseBase):

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null_and_empty_values(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        for field, value in data.items():
            if value is None:
                raise ValueError(f"{field} cannot be null.")

            if isinstance(value, str) and not value.strip():
                raise ValueError(f"{field} cannot be empty.")

        return data


class ExpenseUpdate(BaseModel):
    category: ExpenseCategoryEnum | None = None
    sub_category: str | None = Field(default=None, min_length=1, max_length=100)
    expense_date: datetime | None = None
    amount: Decimal | None = Field(default=None, gt=0)

    description: str | None = None

    vendor_id: int | None = Field(default=None, gt=0)
    invoice_number: str | None = Field(default=None, max_length=100)
    invoice_date: date | None = None
    gst_number: str | None = Field(default=None, max_length=30)
    gst_amount: Decimal | None = Field(default=None, ge=0)

    cost_center: str | None = Field(default=None, max_length=100)
    project_name: str | None = Field(default=None, max_length=150)
    client_name: str | None = Field(default=None, max_length=150)

    @field_validator(
        "sub_category",
        "description",
        "invoice_number",
        "gst_number",
        "cost_center",
        "project_name",
        "client_name",
        mode="before",
    )
    @classmethod
    def validate_text_fields(cls, value: Any) -> Any:
        if value is None:
            return value

        if not isinstance(value, str):
            raise ValueError("Value must be a string.")

        value = value.strip()

        if not value:
            raise ValueError("Empty or whitespace-only values are not allowed.")

        return value

    @field_validator("expense_date")
    @classmethod
    def validate_expense_date(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.date() >= date.today():
            raise ValueError("Expense date must be earlier than today.")

        return value


class ExpenseOut(BaseModel):
    expense_id: int
    company_id: int
    user_id: int

    category: ExpenseCategoryEnum
    sub_category: str
    expense_date: datetime
    amount: Decimal

    description: str | None = None

    vendor_id: int
    invoice_number: str | None = None
    invoice_date: date | None = None
    gst_number: str | None = None
    gst_amount: Decimal | None = None

    cost_center: str | None = None
    project_name: str | None = None
    client_name: str | None = None

    status: str
    approved_amount: Decimal | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None

    payment_mode: str | None = None
    payment_date: date | None = None
    transaction_reference: str | None = None
    payment_status: str
    paid_by: int | None = None
    closed_at: datetime | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
