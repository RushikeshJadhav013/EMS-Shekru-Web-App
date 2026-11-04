
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.expense import Expense
from app.db.models.vendor import Vendor
from app.enums import ExpenseCategoryEnum


EXPENSE_CATEGORIES = [
    category.value for category in ExpenseCategoryEnum
]

VALID_EXPENSE_STATUSES = {
    "Pending",
    "Approved",
    "Rejected",
    "Paid",
    "Closed",
}

UPDATABLE_FIELDS = {
    "category",
    "sub_category",
    "expense_date",
    "amount",
    "description",
    "vendor_id",
    "invoice_number",
    "invoice_date",
    "gst_number",
    "gst_amount",
    "cost_center",
    "project_name",
    "client_name",
}

REQUIRED_UPDATE_FIELDS = {
    "category",
    "sub_category",
    "expense_date",
    "amount",
    "vendor_id",
}

TEXT_FIELDS = {
    "sub_category",
    "description",
    "invoice_number",
    "gst_number",
    "cost_center",
    "project_name",
    "client_name",
}


def validate_expense_category(
    category: str,
    sub_category: str,
) -> bool:
    if not category or not sub_category:
        return False

    category = category.strip()
    sub_category = sub_category.strip()

    if category not in EXPENSE_CATEGORIES:
        return False

    return bool(sub_category)


def validate_expense_date(expense_date: datetime) -> bool:
    if not isinstance(expense_date, datetime):
        return False

    return expense_date.date() < date.today()


def validate_text_fields(data: dict) -> bool:
    for field in TEXT_FIELDS:
        if field in data:
            value = data[field]

            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    return False

    return True


def get_vendor(
    db: Session,
    vendor_id: int,
    company_id: int,
):
    if not vendor_id or vendor_id <= 0:
        return None

    return (
        db.query(Vendor)
        .filter(
            Vendor.vendor_id == vendor_id,
            Vendor.company_id == company_id,
            Vendor.is_deleted.is_(False),
        )
        .first()
    )


# CREATE EXPENSE
def create_expense(
    db: Session,
    company_id: int,
    user_id: int,
    category: str,
    sub_category: str,
    expense_date: datetime,
    amount: Decimal,
    description: str | None = None,
    vendor_id: int | None = None,
    invoice_number: str | None = None,
    invoice_date: date | None = None,
    gst_number: str | None = None,
    gst_amount: Decimal | None = None,
    cost_center: str | None = None,
    project_name: str | None = None,
    client_name: str | None = None,
):
    data = {
        "sub_category": sub_category,
        "description": description,
        "invoice_number": invoice_number,
        "gst_number": gst_number,
        "cost_center": cost_center,
        "project_name": project_name,
        "client_name": client_name,
    }

    if not validate_text_fields(data):
        return None

    if not validate_expense_category(category, sub_category):
        return None

    if not validate_expense_date(expense_date):
        return None

    if amount is None or amount <= 0:
        return None

    if gst_amount is not None and gst_amount < 0:
        return None

    if not get_vendor(db, vendor_id, company_id):
        return None

    expense = Expense(
        company_id=company_id,
        user_id=user_id,
        category=category.strip(),
        sub_category=sub_category.strip(),
        expense_date=expense_date,
        amount=amount,
        description=description.strip() if description else None,
        vendor_id=vendor_id,
        invoice_number=invoice_number.strip() if invoice_number else None,
        invoice_date=invoice_date,
        gst_number=gst_number.strip() if gst_number else None,
        gst_amount=gst_amount,
        cost_center=cost_center.strip() if cost_center else None,
        project_name=project_name.strip() if project_name else None,
        client_name=client_name.strip() if client_name else None,
        status="Pending",
        payment_status="Unpaid",
    )

    try:
        db.add(expense)
        db.commit()
        db.refresh(expense)
        return expense
    except Exception:
        db.rollback()
        raise


# GET ALL EXPENSES
def get_expenses(
    db: Session,
    company_id: int,
    user_id: int | None = None,
):
    query = db.query(Expense).filter(
        Expense.company_id == company_id
    )

    if user_id is not None:
        query = query.filter(
            Expense.user_id == user_id
        )

    return (
        query
        .order_by(Expense.expense_id.desc())
        .all()
    )


# GET EXPENSE BY ID
def get_expense(
    db: Session,
    expense_id: int,
    company_id: int,
    user_id: int | None = None,
):
    query = db.query(Expense).filter(
        Expense.expense_id == expense_id,
        Expense.company_id == company_id,
    )

    if user_id is not None:
        query = query.filter(
            Expense.user_id == user_id
        )

    return query.first()


# UPDATE EXPENSE
def update_expense(
    db: Session,
    expense_id: int,
    company_id: int,
    **updates,
):
    expense = get_expense(
        db,
        expense_id,
        company_id,
    )

    if (
        expense is None
        or expense.status != "Pending"
        or not updates
    ):
        return None

    if not set(updates).issubset(UPDATABLE_FIELDS):
        return None

    for field in REQUIRED_UPDATE_FIELDS:
        if field in updates and updates[field] is None:
            return None

    if not validate_text_fields(updates):
        return None

    new_category = updates.get(
        "category",
        expense.category,
    )

    new_sub_category = updates.get(
        "sub_category",
        expense.sub_category,
    )

    if not validate_expense_category(
        new_category,
        new_sub_category,
    ):
        return None

    if "category" in updates:
        updates["category"] = updates["category"].strip()

    if "sub_category" in updates:
        updates["sub_category"] = updates["sub_category"].strip()

    if "expense_date" in updates:
        if not validate_expense_date(updates["expense_date"]):
            return None

    vendor_id = updates.get(
        "vendor_id",
        expense.vendor_id,
    )

    if not get_vendor(db, vendor_id, company_id):
        return None

    new_amount = updates.get(
        "amount",
        expense.amount,
    )

    if new_amount is None or new_amount <= 0:
        return None

    gst_amount = updates.get(
        "gst_amount",
        expense.gst_amount,
    )

    if gst_amount is not None and gst_amount < 0:
        return None

    for field, value in updates.items():
        if isinstance(value, str):
            value = value.strip()

        setattr(expense, field, value)

    try:
        db.commit()
        db.refresh(expense)
        return expense
    except Exception:
        db.rollback()
        raise


# DELETE PENDING EXPENSE
def delete_expense(
    db: Session,
    expense_id: int,
    company_id: int,
):
    expense = get_expense(
        db,
        expense_id,
        company_id,
    )

    if expense is None:
        return "not_found"

    if expense.status != "Pending":
        return "not_pending"

    document_paths = [
        Path(document.document_path)
        for document in expense.documents
        if document.document_path
    ]

    try:
        db.delete(expense)
        db.commit()
    except Exception:
        db.rollback()
        raise

    for file_path in document_paths:
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            pass

    return "deleted"


# APPROVE EXPENSE
def approve_expense(
    db: Session,
    expense_id: int,
    company_id: int,
    approved_by: int | None = None,
    approved_amount: Decimal | None = None,
):
    expense = get_expense(
        db,
        expense_id,
        company_id,
    )

    if expense is None or expense.status != "Pending":
        return None

    if not expense.documents:
        return None

    final_amount = (
        approved_amount
        if approved_amount is not None
        else expense.amount
    )

    if final_amount <= 0 or final_amount > expense.amount:
        return None

    expense.status = "Approved"
    expense.approved_amount = final_amount
    expense.approved_by = approved_by
    expense.approved_at = datetime.utcnow()
    expense.rejection_reason = None

    try:
        db.commit()
        db.refresh(expense)
        return expense
    except Exception:
        db.rollback()
        raise


# REJECT EXPENSE
def reject_expense(
    db: Session,
    expense_id: int,
    company_id: int,
    rejection_reason: str,
):
    expense = get_expense(
        db,
        expense_id,
        company_id,
    )

    if expense is None or expense.status != "Pending":
        return None

    if not rejection_reason or not rejection_reason.strip():
        return None

    expense.status = "Rejected"
    expense.rejection_reason = rejection_reason.strip()

    try:
        db.commit()
        db.refresh(expense)
        return expense
    except Exception:
        db.rollback()
        raise


# PAY APPROVED EXPENSE
def pay_expense(
    db: Session,
    expense_id: int,
    company_id: int,
    payment_mode: str,
    payment_date: date,
    transaction_reference: str | None = None,
    paid_by: int | None = None,
):
    expense = get_expense(
        db,
        expense_id,
        company_id,
    )

    if expense is None or expense.status != "Approved":
        return None

    if not payment_mode or not payment_mode.strip():
        return None

    if (
        transaction_reference is not None
        and not transaction_reference.strip()
    ):
        return None

    expense.payment_mode = payment_mode.strip()
    expense.payment_date = payment_date
    expense.transaction_reference = (
        transaction_reference.strip()
        if transaction_reference
        else None
    )
    expense.paid_by = paid_by
    expense.payment_status = "Paid"

    expense.status = "Closed"
    expense.closed_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(expense)
        return expense
    except Exception:
        db.rollback()
        raise


# EXPENSE DASHBOARD
def get_expense_dashboard(
    db: Session,
    company_id: int,
):
    total_count, total_amount = (
        db.query(
            func.count(Expense.expense_id),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .filter(
            Expense.company_id == company_id
        )
        .first()
    )

    status_data = (
        db.query(
            Expense.status,
            func.count(Expense.expense_id),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .filter(
            Expense.company_id == company_id
        )
        .group_by(Expense.status)
        .all()
    )

    status_summary = {
        expense_status: {
            "count": 0,
            "amount": 0,
        }
        for expense_status in VALID_EXPENSE_STATUSES
    }

    for name, count, amount in status_data:
        status_summary[name] = {
            "count": count,
            "amount": amount,
        }

    category_data = (
        db.query(
            Expense.category,
            func.count(Expense.expense_id),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .filter(
            Expense.company_id == company_id
        )
        .group_by(Expense.category)
        .all()
    )

    category_summary = [
        {
            "category_name": category,
            "expense_count": count,
            "total_amount": amount,
        }
        for category, count, amount in category_data
    ]

    return {
        "total_expenses": total_count,
        "total_amount": total_amount,
        "status_summary": status_summary,
        "category_summary": category_summary,
    }
