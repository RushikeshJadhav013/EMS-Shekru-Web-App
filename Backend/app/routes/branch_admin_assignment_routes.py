from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.super_admin import SuperAdmin
from app.db.models.company_branch import CompanyBranch  # noqa: F401
from app.dependencies import get_current_super_admin
from app.crud.branch_admin_assignment_crud import (
    assign_admin_to_branch,
    deactivate_admin_assignment,
    list_active_branch_admins,
)
from app.schemas.branch_admin_assignment_schema import (
    BranchAdminAssignmentCreate,
    BranchAdminAssignmentOut,
)
from app.schemas.user_schema import UserOut


router = APIRouter(prefix="/company-branches", tags=["Branch Admin Assignments"])


@router.post("/{branch_id}/admins", response_model=BranchAdminAssignmentOut, status_code=status.HTTP_201_CREATED)
def assign_admin_to_branch_route(
    branch_id: int,
    payload: BranchAdminAssignmentCreate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    try:
        return assign_admin_to_branch(
            db=db,
            branch_id=branch_id,
            admin=payload,
            created_by=current_super_admin.super_admin_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{branch_id}/admins", response_model=List[UserOut])
def list_branch_admins_route(
    branch_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    # Only active/non-deleted branch admins are returned by CRUD.
    # If you need admin list even for inactive branches, we'll adjust filters.
    return list_active_branch_admins(db=db, branch_id=branch_id)


@router.delete("/{branch_id}/admins/{admin_user_id}", response_model=BranchAdminAssignmentOut)
def remove_branch_admin_route(
    branch_id: int,
    admin_user_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    try:
        return deactivate_admin_assignment(
            db=db,
            branch_id=branch_id,
            admin_user_id=admin_user_id,
            updated_by=current_super_admin.super_admin_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

