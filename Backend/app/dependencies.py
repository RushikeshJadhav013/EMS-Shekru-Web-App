from fastapi import Depends, HTTPException, status, Header
from fastapi.security import APIKeyHeader
from jose import jwt, JWTError
from app.db.database import get_db
from sqlalchemy.orm import Session
from app.db.models.user import User
from app.db.models.super_admin import SuperAdmin
from app.core.config import settings
from app.enums import RoleEnum
from typing import Optional

from app.db.models.branch_admin_assignment import BranchAdminAssignment
from app.db.models.company_admin_assignment import CompanyAdminAssignment
from app.db.models.company_branch import CompanyBranch
from app.crud.company_crud import get_company_by_slug
from app.utils.employee_status import is_ex_employee

api_key_header = APIKeyHeader(name="Authorization")

def get_current_user(token: str = Depends(api_key_header), db: Session = Depends(get_db)) -> User:
    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        # ✅ Check if user is still active (in case they were deactivated after login)
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Account is inactive. Please contact your administrator."
            )

        if is_ex_employee(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account access revoked. This employee has resigned.",
            )

        # Detach authenticated user object so the pooled connection can be released early.
        db.expunge(user)
        return user
    finally:
        db.close()

def get_current_super_admin(token: str = Depends(api_key_header), db: Session = Depends(get_db)) -> SuperAdmin:
    """Verify JWT token and return authenticated super admin"""
    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        
        # Verify the role is super_admin
        if role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Super admin role required."
            )
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    try:
        super_admin = db.query(SuperAdmin).filter(SuperAdmin.email == email).first()
        if not super_admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Super Admin not found")
        
        if not super_admin.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admin account is inactive")

        db.expunge(super_admin)
        return super_admin
    finally:
        db.close()

def require_roles(*roles: RoleEnum):
    """
    Accept roles as variadic args or iterables.
    Some routes pass a list (e.g., require_roles([ADMIN, HR])).
    Normalize to a flat set for membership checks.
    """
    allowed = set()
    for role in roles:
        if isinstance(role, (list, tuple, set)):
            allowed.update(role)
        else:
            allowed.add(role)

    def wrapper(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        return current_user

    return wrapper


def get_tenant_scope(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_branch_id: Optional[int] = Header(default=None, alias="X-Branch-Id"),
    x_company_id: Optional[int] = Header(default=None, alias="X-Company-Id"),
    company_slug: Optional[str] = None,
) -> dict:
    """
    Resolve the effective tenant scope (company_id, optional branch_id) for the current request.

    Rules:
    - Admin users: scope is derived from active admin assignments. If multiple possible scopes exist,
      caller must provide X-Branch-Id or X-Company-Id.
    - Non-admin users: scope is taken from their own user row (company_id/branch_id).
    """
    effective_company_id: Optional[int] = x_company_id

    # If tenant routing uses /{company_slug}, resolve it to company_id here.
    if effective_company_id is None and company_slug is not None:
        resolved_company = get_company_by_slug(db, company_slug)
        if not resolved_company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found for provided slug",
            )
        effective_company_id = int(resolved_company.company_id)

    # Non-admins must already be tied to a company in the users table.
    if getattr(current_user, "role", None) != RoleEnum.ADMIN:
        company_id = getattr(current_user, "company_id", None)
        branch_id = getattr(current_user, "branch_id", None)
        if company_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not assigned to any company. Contact an administrator.",
            )
        if effective_company_id is not None and int(company_id) != effective_company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to access this company (slug mismatch).",
            )
        return {"company_id": int(company_id), "branch_id": int(branch_id) if branch_id is not None else None}

    admin_user_id = int(current_user.user_id)

    # Explicit branch scope
    if x_branch_id is not None:
        branch = (
            db.query(CompanyBranch)
            .join(BranchAdminAssignment, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
            .filter(
                BranchAdminAssignment.admin_user_id == admin_user_id,
                BranchAdminAssignment.is_active == True,  # noqa: E712
                CompanyBranch.branch_id == int(x_branch_id),
                CompanyBranch.is_deleted == False,  # noqa: E712
            )
            .first()
        )
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this branch (or branch is inactive/deleted).",
            )
        return {"company_id": int(branch.company_id), "branch_id": int(branch.branch_id)}

    # Explicit company scope (company-level)
    if effective_company_id is not None:
        company_id = int(effective_company_id)
        has_company_assignment = (
            db.query(CompanyAdminAssignment.assignment_id)
            .filter(
                CompanyAdminAssignment.admin_user_id == admin_user_id,
                CompanyAdminAssignment.company_id == company_id,
                CompanyAdminAssignment.is_active == True,  # noqa: E712
            )
            .first()
            is not None
        )
        has_branch_in_company = (
            db.query(BranchAdminAssignment.assignment_id)
            .join(CompanyBranch, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
            .filter(
                BranchAdminAssignment.admin_user_id == admin_user_id,
                BranchAdminAssignment.is_active == True,  # noqa: E712
                CompanyBranch.company_id == company_id,
                CompanyBranch.is_deleted == False,  # noqa: E712
            )
            .first()
            is not None
        )
        if not (has_company_assignment or has_branch_in_company):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this company.",
            )
        return {"company_id": company_id, "branch_id": None}

    # No explicit scope provided. Infer only if unambiguous.
    active_branch_ids = (
        db.query(CompanyBranch.branch_id, CompanyBranch.company_id)
        .join(BranchAdminAssignment, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
        .filter(
            BranchAdminAssignment.admin_user_id == admin_user_id,
            BranchAdminAssignment.is_active == True,  # noqa: E712
            CompanyBranch.is_deleted == False,  # noqa: E712
        )
        .all()
    )
    active_company_ids = (
        db.query(CompanyAdminAssignment.company_id)
        .filter(
            CompanyAdminAssignment.admin_user_id == admin_user_id,
            CompanyAdminAssignment.is_active == True,  # noqa: E712
        )
        .all()
    )
    branch_scopes = {(int(bid), int(cid)) for (bid, cid) in active_branch_ids}
    company_scopes = {int(cid) for (cid,) in active_company_ids}

    if len(branch_scopes) == 1 and len(company_scopes) == 0:
        (branch_id, company_id) = next(iter(branch_scopes))
        return {"company_id": company_id, "branch_id": branch_id}
    if len(company_scopes) == 1 and len(branch_scopes) == 0:
        company_id = next(iter(company_scopes))
        return {"company_id": company_id, "branch_id": None}

    if len(branch_scopes) == 0 and len(company_scopes) == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin is not assigned to any company or branch.",
        )

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Multiple company/branch assignments found. Provide X-Branch-Id or X-Company-Id to select scope.",
    )
