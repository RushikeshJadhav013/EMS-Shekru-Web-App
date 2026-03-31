from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.company import Company  # noqa: F401
from app.db.models.company_branch import CompanyBranch
from app.db.models.super_admin import SuperAdmin
from app.dependencies import get_current_super_admin
from app.crud.company_branch_crud import (
    create_branch,
    get_branch,
    get_branch_by_contact_number,
    get_branch_by_name,
    list_branches,
    update_branch,
    set_branch_status,
    soft_delete_branch,
)
from app.crud.branch_admin_assignment_crud import get_active_admin_assignments_count
from app.schemas.company_branch_schema import (
    CompanyBranchCreate,
    CompanyBranchUpdate,
    CompanyBranchOut,
    CompanyBranchStatusUpdate,
)

router = APIRouter(prefix="/company-branches", tags=["Company Branches"])


@router.post("", response_model=CompanyBranchOut, status_code=status.HTTP_201_CREATED)
def create_branch_route(
    branch: CompanyBranchCreate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    # Create branch as inactive initially; admins will be assigned next.
    branch.status = False

    # Uniqueness (superadmin only)
    existing_name = get_branch_by_name(
        db=db,
        company_id=branch.company_id,
        branch_name=branch.branch_name,
        include_deleted=True,
    )
    if existing_name:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Branch name already exists")

    existing_contact = get_branch_by_contact_number(
        db=db,
        company_id=None,
        contact_number=branch.contact_number,
        include_deleted=True,
    )
    if existing_contact:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Branch contact number already exists"
        )

    return create_branch(db, branch, created_by=current_super_admin.super_admin_id)


@router.get("", response_model=List[CompanyBranchOut])
def list_branches_route(
    company_id: int | None = None,
    include_deleted: bool = False,
    status_filter: bool | None = None,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    return list_branches(
        db=db,
        company_id=company_id,
        include_deleted=include_deleted,
        status=status_filter,
    )


@router.get("/{branch_id}", response_model=CompanyBranchOut)
def get_branch_route(
    branch_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    branch = get_branch(db, branch_id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


@router.put("/{branch_id}", response_model=CompanyBranchOut)
def update_branch_route(
    branch_id: int,
    branch_update: CompanyBranchUpdate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    branch = get_branch(db, branch_id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    # Uniqueness checks (soft-delete aware)
    if branch_update.branch_name is not None:
        existing_name = get_branch_by_name(
            db=db,
            company_id=branch.company_id,
            branch_name=branch_update.branch_name,
            include_deleted=True,
        )
        if existing_name and existing_name.branch_id != branch_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Branch name already exists")

    if branch_update.contact_number is not None:
        existing_contact = get_branch_by_contact_number(
            db=db,
            company_id=None,
            contact_number=branch_update.contact_number,
            include_deleted=True,
        )
        if existing_contact and existing_contact.branch_id != branch_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Branch contact number already exists"
            )

    updated = update_branch(db, branch_id, branch_update, updated_by=current_super_admin.super_admin_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return updated


@router.patch("/{branch_id}/status", response_model=CompanyBranchOut)
def set_branch_status_route(
    branch_id: int,
    payload: CompanyBranchStatusUpdate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    # Enforce rule: an active branch must always have at least one active admin assignment.
    if payload.status:
        active_admins = get_active_admin_assignments_count(db, branch_id)
        if active_admins <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot activate branch without at least one active admin",
            )

    updated = set_branch_status(
        db, branch_id, payload.status, updated_by=current_super_admin.super_admin_id
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return updated


@router.delete("/{branch_id}", response_model=CompanyBranchOut)
def soft_delete_branch_route(
    branch_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    deleted = soft_delete_branch(db, branch_id, updated_by=current_super_admin.super_admin_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return deleted

