
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models.expense import Expense
from app.db.models.vendor import Vendor
from app.enums import ExpenseCategoryEnum


EXPENSE_CATEGORIES = [category.value for category in ExpenseCategoryEnum]

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
}


def validate_expense_category(category: str, sub_category: str) -> bool:
    if category not in EXPENSE_CATEGORIES:
        return False

    return bool(sub_category and sub_category.strip())


def get_vendor(db: Session, vendor_id: int, company_id: int):
    return (
        db.query(Vendor)
        .filter(
            Vendor.vendor_id == vendor_id,
            Vendor.company_id == company_id,
        )
        .first()
    )


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
    if not validate_expense_category(category, sub_category):
        return None

    if amount <= 0:
        return None

    if gst_amount is not None and gst_amount < 0:
        return None

    if vendor_id is not None and not get_vendor(db, vendor_id, company_id):
        return None

    expense = Expense(
        company_id=company_id,
        user_id=user_id,
        category=category,
        sub_category=sub_category.strip(),
        expense_date=expense_date,
        amount=amount,
        description=description,
        vendor_id=vendor_id,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        gst_number=gst_number,
        gst_amount=gst_amount,
        cost_center=cost_center,
        project_name=project_name,
        client_name=client_name,
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


def get_expenses(
    db: Session,
    company_id: int,
    status: str | None = None,
    category: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
    user_id: int | None = None,
):
    query = db.query(Expense).filter(Expense.company_id == company_id)

    if user_id is not None:
        query = query.filter(Expense.user_id == user_id)

    if status == "Paid":
        query = query.filter(Expense.payment_status == "Paid")
    elif status:
        query = query.filter(Expense.status == status)

    if category:
        query = query.filter(Expense.category == category)

    if start_date:
        query = query.filter(
            Expense.expense_date >= datetime.combine(start_date, time.min)
        )

    if end_date:
        query = query.filter(
            Expense.expense_date
            < datetime.combine(end_date + timedelta(days=1), time.min)
        )

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Expense.description.ilike(term),
                Expense.category.ilike(term),
                Expense.sub_category.ilike(term),
                Expense.invoice_number.ilike(term),
                Expense.vendor.has(Vendor.vendor_name.ilike(term)),
            )
        )

    total = query.count()

    expenses = (
        query.order_by(Expense.expense_id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit,
        "expenses": expenses,
    }


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
        query = query.filter(Expense.user_id == user_id)

    return query.first()


def update_expense(
    db: Session,
    expense_id: int,
    company_id: int,
    **updates,
):
    expense = get_expense(db, expense_id, company_id)

    if expense is None or expense.status != "Pending" or not updates:
        return None

    if not set(updates).issubset(UPDATABLE_FIELDS):
        return None

    for field in REQUIRED_UPDATE_FIELDS:
        if field in updates and updates[field] is None:
            return None

    new_category = updates.get("category", expense.category)
    new_sub_category = updates.get("sub_category", expense.sub_category)

    if not validate_expense_category(new_category, new_sub_category):
        return None

    if "sub_category" in updates:
        updates["sub_category"] = updates["sub_category"].strip()

    vendor_id = updates.get("vendor_id", expense.vendor_id)

    if vendor_id is not None and not get_vendor(db, vendor_id, company_id):
        return None

    if updates.get("amount", expense.amount) <= 0:
        return None

    gst_amount = updates.get("gst_amount", expense.gst_amount)

    if gst_amount is not None and gst_amount < 0:
        return None

    for field, value in updates.items():
        setattr(expense, field, value)

    try:
        db.commit()
        db.refresh(expense)
        return expense
    except Exception:
        db.rollback()
        raise


def delete_expense(
    db: Session,
    expense_id: int,
    company_id: int,
):
    expense = get_expense(db, expense_id, company_id)

    if expense is None or expense.status != "Pending":
        return None

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

    return True


def approve_expense(
    db: Session,
    expense_id: int,
    company_id: int,
    approved_by: int | None = None,
    approved_amount: Decimal | None = None,
):
    expense = get_expense(db, expense_id, company_id)

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


def reject_expense(
    db: Session,
    expense_id: int,
    company_id: int,
    rejection_reason: str,
):
    expense = get_expense(db, expense_id, company_id)
    reason = rejection_reason.strip()

    if expense is None or expense.status != "Pending" or not reason:
        return None

    expense.status = "Rejected"
    expense.rejection_reason = reason

    try:
        db.commit()
        db.refresh(expense)
        return expense
    except Exception:
        db.rollback()
        raise


def pay_expense(
    db: Session,
    expense_id: int,
    company_id: int,
    payment_mode: str,
    payment_date: date,
    transaction_reference: str | None = None,
    paid_by: int | None = None,
):
    expense = get_expense(db, expense_id, company_id)

    if expense is None or expense.status != "Approved":
        return None

    if not payment_mode or not payment_mode.strip():
        return None

    expense.payment_mode = payment_mode.strip()
    expense.payment_date = payment_date
    expense.transaction_reference = transaction_reference
    expense.paid_by = paid_by
    expense.payment_status = "Paid"

    # Automatically close the expense after successful payment.
    expense.status = "Closed"
    expense.closed_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(expense)
        return expense
    except Exception:
        db.rollback()
        raise


def get_expense_dashboard(
    db: Session,
    company_id: int,
):
    total_count, total_amount = (
        db.query(
            func.count(Expense.expense_id),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .filter(Expense.company_id == company_id)
        .first()
    )

    status_data = (
        db.query(
            Expense.status,
            func.count(Expense.expense_id),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .filter(Expense.company_id == company_id)
        .group_by(Expense.status)
        .all()
    )

    status_summary = {
        expense_status: {"count": 0, "amount": 0}
        for expense_status in VALID_EXPENSE_STATUSES
    }

    for name, count, amount in status_data:
        status_summary[name] = {"count": count, "amount": amount}

    category_data = (
        db.query(
            Expense.category,
            func.count(Expense.expense_id),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .filter(Expense.company_id == company_id)
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