from datetime import date, datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.enums import ExpenseCategoryEnum


EXPENSE_CATEGORIES = {
    category.value for category in ExpenseCategoryEnum
}


class ExpenseBase(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    sub_category: str = Field(..., min_length=1, max_length=100)
    expense_date: datetime
    amount: Decimal = Field(..., gt=0)
    description: str | None = None

    vendor_id: int | None = Field(default=None, gt=0)
    invoice_number: str | None = Field(default=None, max_length=100)
    invoice_date: date | None = None
    gst_number: str | None = Field(default=None, max_length=30)
    gst_amount: Decimal | None = Field(default=None, ge=0)

    cost_center: str | None = Field(default=None, max_length=100)
    project_name: str | None = Field(default=None, max_length=150)
    client_name: str | None = Field(default=None, max_length=150)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = value.strip()

        if value not in EXPENSE_CATEGORIES:
            raise ValueError("Invalid expense category.")

        return value

    @field_validator("sub_category")
    @classmethod
    def validate_sub_category(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Sub-category cannot be empty.")

        return value


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=100)
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

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str | None) -> str | None:
        if value is None:
            return value

        value = value.strip()

        if value not in EXPENSE_CATEGORIES:
            raise ValueError("Invalid expense category.")

        return value

    @field_validator("sub_category")
    @classmethod
    def validate_sub_category(cls, value: str | None) -> str | None:
        if value is None:
            return value

        value = value.strip()

        if not value:
            raise ValueError("Sub-category cannot be empty.")

        return value


class ExpenseOut(ExpenseBase):
    expense_id: int
    company_id: int
    user_id: int
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
