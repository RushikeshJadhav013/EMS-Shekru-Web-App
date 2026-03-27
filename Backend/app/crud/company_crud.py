from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models.company import Company
from app.schemas.company_schema import CompanyCreate, CompanyUpdate


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def create_company(db: Session, company: CompanyCreate, created_by: int | None = None) -> Company:
    payload = company.model_dump()
    payload["company_email"] = _normalize_email(payload.get("company_email"))
    db_company = Company(**payload, created_by=created_by)
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company


def get_company(db: Session, company_id: int, include_deleted: bool = False) -> Company | None:
    q = db.query(Company).filter(Company.company_id == company_id)
    if not include_deleted:
        q = q.filter(Company.is_deleted == False)  # noqa: E712
    return q.first()


def get_company_by_email(db: Session, company_email: str, include_deleted: bool = False) -> Company | None:
    normalized = _normalize_email(company_email)
    q = db.query(Company).filter(func.lower(Company.company_email) == normalized)
    if not include_deleted:
        q = q.filter(Company.is_deleted == False)  # noqa: E712
    return q.first()


def get_company_by_contact_number(
    db: Session,
    contact_number: str,
    include_deleted: bool = False,
) -> Company | None:
    normalized = (contact_number or "").strip()
    q = db.query(Company).filter(Company.contact_number == normalized)
    if not include_deleted:
        q = q.filter(Company.is_deleted == False)  # noqa: E712
    return q.first()


def get_company_by_gst_no(
    db: Session,
    gst_no: str | None,
    include_deleted: bool = False,
) -> Company | None:
    if gst_no is None:
        return None
    normalized = gst_no.strip().upper()
    q = db.query(Company).filter(Company.gst_no == normalized)
    if not include_deleted:
        q = q.filter(Company.is_deleted == False)  # noqa: E712
    return q.first()


def list_companies(
    db: Session,
    include_deleted: bool = False,
    status: bool | None = None,
) -> list[Company]:
    q = db.query(Company)
    if not include_deleted:
        q = q.filter(Company.is_deleted == False)  # noqa: E712
    if status is not None:
        q = q.filter(Company.status == status)
    return q.order_by(Company.created_at.desc()).all()


def update_company(
    db: Session,
    company_id: int,
    company_update: CompanyUpdate,
    updated_by: int | None = None,
) -> Company | None:
    company = get_company(db, company_id)
    if not company:
        return None

    data = company_update.model_dump(exclude_unset=True)
    if "company_email" in data:
        data["company_email"] = _normalize_email(data["company_email"])

    for key, value in data.items():
        setattr(company, key, value)
    company.updated_by = updated_by
    db.commit()
    db.refresh(company)
    return company


def set_company_status(db: Session, company_id: int, status: bool, updated_by: int | None = None) -> Company | None:
    company = get_company(db, company_id)
    if not company:
        return None
    company.status = status
    company.updated_by = updated_by
    db.commit()
    db.refresh(company)
    return company


def soft_delete_company(db: Session, company_id: int, updated_by: int | None = None) -> Company | None:
    company = get_company(db, company_id)
    if not company:
        return None
    company.is_deleted = True
    company.updated_by = updated_by
    db.commit()
    db.refresh(company)
    return company
