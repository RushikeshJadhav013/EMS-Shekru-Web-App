
from sqlalchemy.orm import Session

from app.db.models.expense import Expense
from app.db.models.expense_document import ExpenseDocument


def create_expense_document(
    db: Session,
    expense_id: int,
    company_id: int,
    document_name: str,
    document_path: str,
    document_type: str | None = None,
    uploaded_by: int | None = None,
):
    expense = (
        db.query(Expense)
        .filter(
            Expense.expense_id == expense_id,
            Expense.company_id == company_id,
        )
        .first()
    )

    if not expense or expense.status != "Pending":
        return None

    if not document_name.strip() or not document_path.strip():
        return None

    document = ExpenseDocument(
        expense_id=expense_id,
        document_name=document_name.strip(),
        document_path=document_path.strip(),
        document_type=document_type,
        uploaded_by=uploaded_by,
    )

    try:
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        raise


def get_expense_documents(
    db: Session,
    expense_id: int,
    company_id: int,
):
    expense = (
        db.query(Expense)
        .filter(
            Expense.expense_id == expense_id,
            Expense.company_id == company_id,
        )
        .first()
    )

    if not expense:
        return None

    return (
        db.query(ExpenseDocument)
        .filter(ExpenseDocument.expense_id == expense_id)
        .order_by(ExpenseDocument.uploaded_at.desc())
        .all()
    )


def get_expense_document(
    db: Session,
    document_id: int,
    expense_id: int,
    company_id: int,
):
    expense = (
        db.query(Expense)
        .filter(
            Expense.expense_id == expense_id,
            Expense.company_id == company_id,
        )
        .first()
    )

    if not expense:
        return None

    return (
        db.query(ExpenseDocument)
        .filter(
            ExpenseDocument.document_id == document_id,
            ExpenseDocument.expense_id == expense_id,
        )
        .first()
    )


def delete_expense_document(
    db: Session,
    document: ExpenseDocument,
):
    try:
        db.delete(document)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
