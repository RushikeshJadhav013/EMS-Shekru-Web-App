from sqlalchemy.orm import Session

from app.db.models.company import Company
from app.db.models.company_admin_assignment import CompanyAdminAssignment
from app.db.models.user import User
from app.enums import RoleEnum
from app.schemas.company_admin_assignment_schema import CompanyAdminAssignmentCreate


def assign_admin_to_company(
    db: Session,
    company_id: int,
    admin: CompanyAdminAssignmentCreate,
    created_by: int | None = None,
) -> CompanyAdminAssignment:
    company = (
        db.query(Company)
        .filter(
            Company.company_id == company_id,
            Company.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not company:
        raise ValueError("Company not found")

    admin_user = (
        db.query(User)
        .filter(
            User.user_id == admin.admin_user_id,
            User.role == RoleEnum.ADMIN,
        )
        .first()
    )
    if not admin_user:
        raise ValueError("Admin user not found or user is not an admin")

    existing = (
        db.query(CompanyAdminAssignment)
        .filter(
            CompanyAdminAssignment.company_id == company_id,
            CompanyAdminAssignment.admin_user_id == admin.admin_user_id,
        )
        .first()
    )
    if existing:
        if existing.is_active:
            raise ValueError("Admin is already assigned to this company")
        existing.is_active = True
        existing.updated_by = created_by
        db.commit()
        db.refresh(existing)
        return existing

    db_assignment = CompanyAdminAssignment(
        admin_user_id=admin.admin_user_id,
        company_id=company_id,
        is_active=True,
        created_by=created_by,
    )
    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)
    return db_assignment


def deactivate_company_admin_assignment(
    db: Session,
    company_id: int,
    admin_user_id: int,
    updated_by: int | None = None,
) -> CompanyAdminAssignment:
    assignment = (
        db.query(CompanyAdminAssignment)
        .filter(
            CompanyAdminAssignment.company_id == company_id,
            CompanyAdminAssignment.admin_user_id == admin_user_id,
        )
        .first()
    )
    if not assignment:
        raise ValueError("Company admin assignment not found")

    assignment.is_active = False
    assignment.updated_by = updated_by
    db.commit()
    db.refresh(assignment)
    return assignment


def list_active_company_level_admins(db: Session, company_id: int) -> list[User]:
    admins = (
        db.query(User)
        .join(CompanyAdminAssignment, CompanyAdminAssignment.admin_user_id == User.user_id)
        .filter(
            CompanyAdminAssignment.company_id == company_id,
            CompanyAdminAssignment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.role == RoleEnum.ADMIN,
        )
        .order_by(User.user_id.asc())
        .all()
    )
    return admins


def count_active_company_level_assignments(db: Session, company_id: int) -> int:
    return (
        db.query(CompanyAdminAssignment)
        .join(User, CompanyAdminAssignment.admin_user_id == User.user_id)
        .filter(
            CompanyAdminAssignment.company_id == company_id,
            CompanyAdminAssignment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.role == RoleEnum.ADMIN,
        )
        .count()
    )
