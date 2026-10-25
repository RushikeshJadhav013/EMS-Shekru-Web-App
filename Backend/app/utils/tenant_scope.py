from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from app.db.models.branch_admin_assignment import BranchAdminAssignment
from app.db.models.company_admin_assignment import CompanyAdminAssignment
from app.db.models.company_branch import CompanyBranch
from app.db.models.user import User
from app.enums import RoleEnum


def admin_assigned_to_company_exists(
    user_alias=User,
    *,
    company_id: int,
    branch_id: int | None = None,
):
    """True when the user is an active admin of the company (direct or via branch)."""
    company_admin = exists(
        select(CompanyAdminAssignment.assignment_id).where(
            CompanyAdminAssignment.admin_user_id == user_alias.user_id,
            CompanyAdminAssignment.company_id == int(company_id),
            CompanyAdminAssignment.is_active.is_(True),
        )
    )
    branch_filters = [
        BranchAdminAssignment.admin_user_id == user_alias.user_id,
        BranchAdminAssignment.is_active.is_(True),
        CompanyBranch.company_id == int(company_id),
        CompanyBranch.is_deleted.is_(False),
    ]
    if branch_id is not None:
        branch_filters.append(BranchAdminAssignment.branch_id == int(branch_id))
    branch_admin = exists(
        select(BranchAdminAssignment.assignment_id)
        .select_from(BranchAdminAssignment)
        .join(CompanyBranch, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
        .where(*branch_filters)
    )
    return or_(company_admin, branch_admin)


def user_in_tenant_scope_clauses(
    *,
    company_id: int | None,
    branch_id: int | None = None,
    user_alias=User,
    include_assigned_admins: bool = True,
) -> list:
    """
    Employee rows match users.company_id / users.branch_id.
    Admins often have NULL company_id; include them via assignments when requested.
    """
    if company_id is None and branch_id is None:
        return []

    direct_parts = []
    if company_id is not None:
        direct_parts.append(user_alias.company_id == int(company_id))
    if branch_id is not None:
        direct_parts.append(user_alias.branch_id == int(branch_id))
    direct = and_(*direct_parts) if len(direct_parts) > 1 else direct_parts[0]

    if not include_assigned_admins or company_id is None:
        return [direct]

    return [
        or_(
            direct,
            and_(
                user_alias.role == RoleEnum.ADMIN,
                admin_assigned_to_company_exists(
                    user_alias, company_id=int(company_id), branch_id=branch_id
                ),
            ),
        )
    ]


def user_in_tenant_scope(
    db: Session,
    *,
    user_id: int,
    company_id: int | None,
    branch_id: int | None = None,
    include_assigned_admins: bool = True,
    require_active: bool = True,
) -> bool:
    if company_id is None and branch_id is None:
        return True
    q = db.query(User.user_id).filter(User.user_id == int(user_id))
    if require_active:
        q = q.filter(User.is_active.is_(True))
    for clause in user_in_tenant_scope_clauses(
        company_id=company_id,
        branch_id=branch_id,
        include_assigned_admins=include_assigned_admins,
    ):
        q = q.filter(clause)
    return q.first() is not None


def assigned_company_admins(
    db: Session,
    company_id: int | None,
    *,
    exclude_user_id: int | None = None,
) -> list[User]:
    """Active admins assigned to this company (not every admin in the system)."""
    if company_id is None:
        return []
    from app.crud.branch_admin_assignment_crud import list_company_assigned_admins

    admins = list_company_assigned_admins(db, int(company_id))
    if exclude_user_id is None:
        return admins
    return [admin for admin in admins if int(admin.user_id) != int(exclude_user_id)]
