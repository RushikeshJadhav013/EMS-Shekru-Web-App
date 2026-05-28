from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models.company_branch import CompanyBranch
from app.schemas.company_branch_schema import CompanyBranchCreate, CompanyBranchUpdate


def _normalize_email(email: str | None) -> str | None:
    if email is None:
        return None
    value = email.strip().lower()
    return value or None


def create_branch(db: Session, branch: CompanyBranchCreate, created_by: int | None = None) -> CompanyBranch:
    payload = branch.model_dump()
    payload["branch_name"] = payload["branch_name"].strip()
    if payload.get("branch_email"):
        payload["branch_email"] = _normalize_email(payload["branch_email"])
    payload["contact_number"] = payload["contact_number"].strip()
    payload["address"] = payload["address"].strip()

    db_branch = CompanyBranch(**payload, created_by=created_by)
    db.add(db_branch)
    db.commit()
    db.refresh(db_branch)
    return db_branch


def get_branch(db: Session, branch_id: int, include_deleted: bool = False) -> CompanyBranch | None:
    q = db.query(CompanyBranch).filter(CompanyBranch.branch_id == branch_id)
    if not include_deleted:
        q = q.filter(CompanyBranch.is_deleted == False)  # noqa: E712
    return q.first()


def get_branch_by_name(
    db: Session,
    company_id: int,
    branch_name: str,
    include_deleted: bool = False,
) -> CompanyBranch | None:
    normalized_name = branch_name.strip()
    q = db.query(CompanyBranch).filter(
        CompanyBranch.company_id == company_id,
        func.lower(CompanyBranch.branch_name) == normalized_name.lower(),
    )
    if not include_deleted:
        q = q.filter(CompanyBranch.is_deleted == False)  # noqa: E712
    return q.first()


def get_branch_by_email(
    db: Session,
    branch_email: str | None,
    include_deleted: bool = False,
) -> CompanyBranch | None:
    normalized = _normalize_email(branch_email)
    if normalized is None:
        return None
    q = db.query(CompanyBranch).filter(func.lower(CompanyBranch.branch_email) == normalized)
    if not include_deleted:
        q = q.filter(CompanyBranch.is_deleted == False)  # noqa: E712
    return q.first()


def get_branch_by_contact_number(
    db: Session,
    company_id: int | None,
    contact_number: str,
    include_deleted: bool = False,
) -> CompanyBranch | None:
    normalized_contact = contact_number.strip()
    # Global uniqueness: ignore company_id when looking up contact_number conflicts.
    q = db.query(CompanyBranch).filter(CompanyBranch.contact_number == normalized_contact)
    if not include_deleted:
        q = q.filter(CompanyBranch.is_deleted == False)  # noqa: E712
    return q.first()


def list_branches(
    db: Session,
    company_id: int | None = None,
    include_deleted: bool = False,
    status: bool | None = None,
) -> list[CompanyBranch]:
    q = db.query(CompanyBranch)
    if company_id is not None:
        q = q.filter(CompanyBranch.company_id == company_id)
    if not include_deleted:
        q = q.filter(CompanyBranch.is_deleted == False)  # noqa: E712
    if status is not None:
        q = q.filter(CompanyBranch.status == status)
    return q.order_by(CompanyBranch.created_at.desc()).all()


def count_branches(db: Session, company_id: int, include_deleted: bool = False) -> int:
    q = db.query(CompanyBranch).filter(CompanyBranch.company_id == company_id)
    if not include_deleted:
        q = q.filter(CompanyBranch.is_deleted == False)  # noqa: E712
    return q.count()


def update_branch(
    db: Session,
    branch_id: int,
    branch_update: CompanyBranchUpdate,
    updated_by: int | None = None,
) -> CompanyBranch | None:
    branch = get_branch(db, branch_id)
    if not branch:
        return None

    data = branch_update.model_dump(exclude_unset=True)
    if "branch_name" in data and data["branch_name"] is not None:
        data["branch_name"] = data["branch_name"].strip()
    if "branch_email" in data and data["branch_email"] is not None:
        data["branch_email"] = _normalize_email(data["branch_email"])
    if "contact_number" in data and data["contact_number"] is not None:
        data["contact_number"] = data["contact_number"].strip()
    if "address" in data and data["address"] is not None:
        data["address"] = data["address"].strip()

    for key, value in data.items():
        setattr(branch, key, value)
    branch.updated_by = updated_by
    db.commit()
    db.refresh(branch)
    return branch


def set_branch_status(db: Session, branch_id: int, status: bool, updated_by: int | None = None) -> CompanyBranch | None:
    branch = get_branch(db, branch_id)
    if not branch:
        return None
    branch.status = status
    branch.updated_by = updated_by
    db.commit()
    db.refresh(branch)
    return branch


def soft_delete_branch(db: Session, branch_id: int, updated_by: int | None = None) -> CompanyBranch | None:
    branch = get_branch(db, branch_id)
    if not branch:
        return None
    branch.is_deleted = True
    branch.updated_by = updated_by
    db.commit()
    db.refresh(branch)
    return branch
