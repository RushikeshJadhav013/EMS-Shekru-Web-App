from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.db.models.branch_admin_assignment import BranchAdminAssignment
from app.db.models.company_branch import CompanyBranch
from app.db.models.user import User
from app.enums import RoleEnum
from app.schemas.branch_admin_assignment_schema import BranchAdminAssignmentCreate


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
        db.commit()
        db.refresh(existing)
        return existing

    db_assignment = BranchAdminAssignment(
        admin_user_id=admin.admin_user_id,
        branch_id=branch_id,
        is_active=True,
        created_by=created_by,
    )
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

