
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Path,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies import (
    get_current_user,
    get_tenant_scope,
    require_roles,
)
from app.enums import RoleEnum
from app.db.models.user import User

from app.schemas.expense_schema import (
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
)

from app.crud.expense_crud import (
    EXPENSE_CATEGORIES,
    create_expense,
    get_expenses,
    get_expense,
    update_expense,
    delete_expense,
    approve_expense,
    reject_expense,
    pay_expense,
    get_expense_dashboard,
)


router = APIRouter(
    prefix="/expenses",
    tags=["Expenses"],
)


class ExpenseReject(BaseModel):
    rejection_reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
    )


class ExpenseApprove(BaseModel):
    approved_amount: Decimal | None = Field(
        default=None,
        gt=0,
    )


class ExpensePayment(BaseModel):
    payment_mode: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )
    payment_date: date
    transaction_reference: str | None = Field(
        default=None,
        max_length=150,
    )


def get_company_id(scope: dict) -> int:
    company_id = scope.get("company_id")

    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company scope is missing.",
        )

    return int(company_id)


# FIXED EXPENSE CATEGORIES
@router.get("/categories")
def get_expense_categories(
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    return {
        "categories": EXPENSE_CATEGORIES
    }


# CREATE EXPENSE
@router.post(
    "/",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_expense_record(
    expense: Annotated[ExpenseCreate, Form()],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    if current_user.role == RoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin is not allowed to create expenses.",
        )

    created = create_expense(
        db=db,
        company_id=get_company_id(scope),
        user_id=current_user.user_id,
        category=expense.category,
        sub_category=expense.sub_category,
        expense_date=expense.expense_date,
        amount=expense.amount,
        description=expense.description,
        vendor_id=expense.vendor_id,
        invoice_number=expense.invoice_number,
        invoice_date=expense.invoice_date,
        gst_number=expense.gst_number,
        gst_amount=expense.gst_amount,
        cost_center=expense.cost_center,
        project_name=expense.project_name,
        client_name=expense.client_name,
    )

    if created is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid category, sub-category, expense date, "
                "amount, or vendor for this company."
            ),
        )

    return created


# GET ALL EXPENSES - WITHOUT FILTERS AND PAGINATION
@router.get(
    "/",
    response_model=list[ExpenseOut],
)
def list_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.ADMIN)
    ),
    scope: dict = Depends(get_tenant_scope),
):
    return get_expenses(
        db=db,
        company_id=get_company_id(scope),
    )


# EXPENSE DASHBOARD
@router.get("/dashboard")
def expense_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.ADMIN)
    ),
    scope: dict = Depends(get_tenant_scope),
):
    return get_expense_dashboard(
        db=db,
        company_id=get_company_id(scope),
    )


# GET EXPENSE BY ID
@router.get(
    "/{expense_id}",
    response_model=ExpenseOut,
)
def get_expense_record(
    expense_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.ADMIN)
    ),
    scope: dict = Depends(get_tenant_scope),
):
    expense = get_expense(
        db=db,
        expense_id=expense_id,
        company_id=get_company_id(scope),
    )

    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found.",
        )

    return expense


# UPDATE PENDING EXPENSE
@router.put(
    "/{expense_id}",
    response_model=ExpenseOut,
)
def update_expense_record(
    expense: ExpenseUpdate,
    expense_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.ADMIN)
    ),
    scope: dict = Depends(get_tenant_scope),
):
    update_data = expense.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update.",
        )

    updated = update_expense(
        db=db,
        expense_id=expense_id,
        company_id=get_company_id(scope),
        **update_data,
    )

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Expense not found, invalid category/sub-category "
                "or vendor, or expense is not Pending."
            ),
        )

    return updated


# DELETE PENDING EXPENSE
@router.delete(
    "/{expense_id}",
    status_code=status.HTTP_200_OK,
)
def delete_expense_record(
    expense_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.ADMIN)
    ),
    scope: dict = Depends(get_tenant_scope),
):
    result = delete_expense(
        db=db,
        expense_id=expense_id,
        company_id=get_company_id(scope),
    )

    if result == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found.",
        )

    if result == "not_pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only Pending expenses can be deleted.",
        )

    return {
        "message": "Expense deleted successfully."
    }


# APPROVE EXPENSE
@router.post(
    "/{expense_id}/approve",
    response_model=ExpenseOut,
)
def approve_expense_record(
    expense_id: int = Path(..., gt=0),
    approval: ExpenseApprove | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.ADMIN)
    ),
    scope: dict = Depends(get_tenant_scope),
):
    company_id = get_company_id(scope)

    existing_expense = get_expense(
        db=db,
        expense_id=expense_id,
        company_id=company_id,
    )

    if existing_expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found.",
        )

    if existing_expense.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Pending expenses can be approved.",
        )

    if not existing_expense.documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Approval cannot proceed until the required "
                "supporting document is attached."
            ),
        )

    expense = approve_expense(
        db=db,
        expense_id=expense_id,
        company_id=company_id,
        approved_by=current_user.user_id,
        approved_amount=(
            approval.approved_amount
            if approval is not None
            else None
        ),
    )

    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid approved amount. It must be greater "
                "than zero and cannot exceed the expense amount."
            ),
        )

    return expense


# REJECT EXPENSE
@router.post(
    "/{expense_id}/reject",
    response_model=ExpenseOut,
)
def reject_expense_record(
    rejection: ExpenseReject,
    expense_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.ADMIN)
    ),
    scope: dict = Depends(get_tenant_scope),
):
    reason = rejection.rejection_reason.strip()

    if not reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rejection reason cannot be empty.",
        )

    expense = reject_expense(
        db=db,
        expense_id=expense_id,
        company_id=get_company_id(scope),
        rejection_reason=reason,
    )

    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Expense not found or only Pending "
                "expenses can be rejected."
            ),
        )

    return expense


# PAY APPROVED EXPENSE
@router.post(
    "/{expense_id}/pay",
    response_model=ExpenseOut,
)
def pay_expense_record(
    payment: ExpensePayment,
    expense_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.ADMIN)
    ),
    scope: dict = Depends(get_tenant_scope),
):
    payment_mode = payment.payment_mode.strip()

    if not payment_mode:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payment mode cannot be empty.",
        )

    expense = pay_expense(
        db=db,
        expense_id=expense_id,
        company_id=get_company_id(scope),
        payment_mode=payment_mode,
        payment_date=payment.payment_date,
        transaction_reference=payment.transaction_reference,
        paid_by=current_user.user_id,
    )

    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Expense not found or only Approved "
                "expenses can be paid."
            ),
        )

    return expense
