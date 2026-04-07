from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.branch_admin_assignment import BranchAdminAssignment
from app.db.models.company import Company
from app.db.models.company_admin_assignment import CompanyAdminAssignment
from app.db.models.company_branch import CompanyBranch
from app.db.models.user import User
from app.enums import RoleEnum
from app.schemas.branch_admin_assignment_schema import BranchAdminAssignmentCreate
from app.crud.company_admin_assignment_crud import (
    count_active_company_level_assignments,
    list_active_company_level_admins,
)


def get_active_admin_assignments_count(db: Session, branch_id: int, exclude_admin_user_id: int | None = None) -> int:
    """
    Count active admin assignments for a branch.

    Counts active admin assignments for the branch.

    "Must have at least one admin" enforcement for *active* branches is done
    by checking the branch.status in the calling function (e.g., on activation/deactivation).
    - assignments.is_active == True
    - assigned user is active and role is ADMIN
    """
    q = (
        db.query(func.count(BranchAdminAssignment.assignment_id))
        .join(User, BranchAdminAssignment.admin_user_id == User.user_id)
        .join(CompanyBranch, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
        .filter(
            BranchAdminAssignment.branch_id == branch_id,
            BranchAdminAssignment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.role == RoleEnum.ADMIN,
            CompanyBranch.is_deleted == False,  # noqa: E712
        )
    )
    if exclude_admin_user_id is not None:
        q = q.filter(BranchAdminAssignment.admin_user_id != exclude_admin_user_id)
    return int(q.scalar() or 0)


def list_active_branch_admins(db: Session, branch_id: int) -> list[User]:
    """
    List active admin users assigned to a branch.
    """
    admins = (
        db.query(User)
        .join(BranchAdminAssignment, BranchAdminAssignment.admin_user_id == User.user_id)
        .join(CompanyBranch, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
        .filter(
            BranchAdminAssignment.branch_id == branch_id,
            BranchAdminAssignment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.role == RoleEnum.ADMIN,
            CompanyBranch.is_deleted == False,  # noqa: E712
        )
        .order_by(User.user_id.asc())
        .all()
    )
    return admins


def assign_admin_to_branch(
    db: Session,
    branch_id: int,
    admin: BranchAdminAssignmentCreate,
    created_by: int | None = None,
) -> BranchAdminAssignment:
    """
    Assign an ADMIN user to a branch.
    Creates assignment if missing, re-activates if previously deactivated.
    """
    # Validate branch exists (and not deleted)
    branch = db.query(CompanyBranch).filter(
        CompanyBranch.branch_id == branch_id,
        CompanyBranch.is_deleted == False,  # noqa: E712
    ).first()
    if not branch:
        raise ValueError("Branch not found")

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
        db.query(BranchAdminAssignment)
        .filter(
            BranchAdminAssignment.branch_id == branch_id,
            BranchAdminAssignment.admin_user_id == admin.admin_user_id,
        )
        .first()
    )
    if existing:
        if existing.is_active:
            raise ValueError("Admin is already assigned to this branch")
        existing.is_active = True
        existing.updated_by = created_by
        # Option A: auto-activate branch when an admin is assigned (or re-activated).
        if not branch.status:
            branch.status = True
            branch.updated_by = created_by
        db.commit()
        db.refresh(existing)
        return existing

    db_assignment = BranchAdminAssignment(
        admin_user_id=admin.admin_user_id,
        branch_id=branch_id,
        is_active=True,
        created_by=created_by,
    )
    # Option A: auto-activate branch when an admin is assigned.
    if not branch.status:
        branch.status = True
        branch.updated_by = created_by
    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)
    return db_assignment


def deactivate_admin_assignment(
    db: Session,
    branch_id: int,
    admin_user_id: int,
    updated_by: int | None = None,
) -> BranchAdminAssignment:
    """
    Deactivate an admin assignment.

    Enforces: if the branch is active, it must keep at least one active admin.
    """
    assignment = (
        db.query(BranchAdminAssignment)
        .filter(
            BranchAdminAssignment.branch_id == branch_id,
            BranchAdminAssignment.admin_user_id == admin_user_id,
        )
        .first()
    )
    if not assignment:
        raise ValueError("Assignment not found")

    if assignment.is_active:
        branch = db.query(CompanyBranch).filter(
            CompanyBranch.branch_id == branch_id,
            CompanyBranch.is_deleted == False,  # noqa: E712
        ).first()
        if branch and branch.status:
            remaining = get_active_admin_assignments_count(
                db, branch_id, exclude_admin_user_id=admin_user_id
            )
            if remaining <= 0:
                raise ValueError("Branch must have at least one active admin")

    assignment.is_active = False
    assignment.updated_by = updated_by
    db.commit()
    db.refresh(assignment)
    return assignment


def list_company_assigned_admins(db: Session, company_id: int) -> list[User]:
    """
    Distinct active admin users assigned to the company:
    via any branch and/or via direct company-level assignment.
    """
    branch_admins = (
        db.query(User)
        .join(BranchAdminAssignment, BranchAdminAssignment.admin_user_id == User.user_id)
        .join(CompanyBranch, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
        .filter(
            CompanyBranch.company_id == company_id,
            CompanyBranch.is_deleted == False,  # noqa: E712
            BranchAdminAssignment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.role == RoleEnum.ADMIN,
        )
        .distinct(User.user_id)
        .order_by(User.user_id.asc())
        .all()
    )
    company_level = list_active_company_level_admins(db, company_id)
    seen = {u.user_id for u in branch_admins}
    merged: list[User] = list(branch_admins)
    for u in company_level:
        if u.user_id not in seen:
            seen.add(u.user_id)
            merged.append(u)
    merged.sort(key=lambda x: x.user_id)
    return merged


def get_company_admin_summary(db: Session, company_id: int) -> dict:
    """
    Summary for a company's branches/admin assignments.
    """
    total_branches = (
        db.query(func.count(CompanyBranch.branch_id))
        .filter(
            CompanyBranch.company_id == company_id,
            CompanyBranch.is_deleted == False,  # noqa: E712
        )
        .scalar()
        or 0
    )
    active_branches = (
        db.query(func.count(CompanyBranch.branch_id))
        .filter(
            CompanyBranch.company_id == company_id,
            CompanyBranch.is_deleted == False,  # noqa: E712
            CompanyBranch.status == True,  # noqa: E712
        )
        .scalar()
        or 0
    )
    branches_with_admin = (
        db.query(func.count(func.distinct(CompanyBranch.branch_id)))
        .join(BranchAdminAssignment, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
        .join(User, BranchAdminAssignment.admin_user_id == User.user_id)
        .filter(
            CompanyBranch.company_id == company_id,
            CompanyBranch.is_deleted == False,  # noqa: E712
            BranchAdminAssignment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.role == RoleEnum.ADMIN,
        )
        .scalar()
        or 0
    )
    branch_admin_user_ids = (
        db.query(User.user_id)
        .join(BranchAdminAssignment, BranchAdminAssignment.admin_user_id == User.user_id)
        .join(CompanyBranch, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
        .filter(
            CompanyBranch.company_id == company_id,
            CompanyBranch.is_deleted == False,  # noqa: E712
            BranchAdminAssignment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.role == RoleEnum.ADMIN,
        )
        .distinct()
        .all()
    )
    company_level_user_ids = (
        db.query(User.user_id)
        .join(CompanyAdminAssignment, CompanyAdminAssignment.admin_user_id == User.user_id)
        .filter(
            CompanyAdminAssignment.company_id == company_id,
            CompanyAdminAssignment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.role == RoleEnum.ADMIN,
        )
        .distinct()
        .all()
    )
    total_assigned_admins = len(
        {uid for (uid,) in branch_admin_user_ids} | {uid for (uid,) in company_level_user_ids}
    )
    company_level_active_assignments = count_active_company_level_assignments(db, company_id)
    branches_without_admin = max(int(total_branches) - int(branches_with_admin), 0)
    return {
        "company_id": company_id,
        "total_branches": int(total_branches),
        "active_branches": int(active_branches),
        "branches_with_admin": int(branches_with_admin),
        "branches_without_admin": int(branches_without_admin),
        "total_assigned_admins": int(total_assigned_admins),
        "active_company_level_admin_assignments": int(company_level_active_assignments),
    }


def list_branches_for_admin(db: Session, admin_user_id: int) -> list[CompanyBranch]:
    """
    Active/non-deleted branches assigned to an admin.
    """
    branches = (
        db.query(CompanyBranch)
        .join(BranchAdminAssignment, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
        .join(User, BranchAdminAssignment.admin_user_id == User.user_id)
        .filter(
            BranchAdminAssignment.admin_user_id == admin_user_id,
            BranchAdminAssignment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.role == RoleEnum.ADMIN,
            CompanyBranch.is_deleted == False,  # noqa: E712
        )
        .distinct(CompanyBranch.branch_id)
        .order_by(CompanyBranch.created_at.desc())
        .all()
    )
    return branches


def list_companies_for_admin(db: Session, admin_user_id: int) -> list[Company]:
    """
    Distinct companies the admin can access via branch assignments and/or direct company assignment.
    """
    from_branch = (
        db.query(Company)
        .join(CompanyBranch, CompanyBranch.company_id == Company.company_id)
        .join(BranchAdminAssignment, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
        .join(User, BranchAdminAssignment.admin_user_id == User.user_id)
        .filter(
            BranchAdminAssignment.admin_user_id == admin_user_id,
            BranchAdminAssignment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.role == RoleEnum.ADMIN,
            CompanyBranch.is_deleted == False,  # noqa: E712
            Company.is_deleted == False,  # noqa: E712
        )
        .distinct(Company.company_id)
        .all()
    )
    from_company = (
        db.query(Company)
        .join(CompanyAdminAssignment, CompanyAdminAssignment.company_id == Company.company_id)
        .join(User, CompanyAdminAssignment.admin_user_id == User.user_id)
        .filter(
            CompanyAdminAssignment.admin_user_id == admin_user_id,
            CompanyAdminAssignment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.role == RoleEnum.ADMIN,
            Company.is_deleted == False,  # noqa: E712
        )
        .distinct(Company.company_id)
        .all()
    )
    by_id: dict[int, Company] = {c.company_id: c for c in from_branch}
    for c in from_company:
        if c.company_id not in by_id:
            by_id[c.company_id] = c
    return sorted(by_id.values(), key=lambda c: c.company_id, reverse=True)

