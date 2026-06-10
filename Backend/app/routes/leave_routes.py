# app/routes/leave_routes.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from typing import Optional, Literal
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta, time
from app.db.database import get_db
from app.utils.timezone import now_ist
from app.crud.leave_crud import (
    apply_leave,
    approve_leave as approve_leave_db,
    list_leave,
    list_leave_by_period,
    update_leave as update_leave_db,
    delete_leave as delete_leave_db,
    list_pending_all,
    list_pending_by_department,
    list_pending_by_requester_roles,
    list_pending_by_department_and_roles,
    list_decided_by_approver,
    create_leave_request_notifications,
    update_leave_request_notifications,
    create_leave_decision_notification,
    create_leave_deletion_notification,
    list_leave_notifications,
    mark_leave_notification_as_read,
    get_leave_balance,
)
from app.crud.leave_config_crud import (
    get_active_leave_config,
    create_leave_config,
    update_leave_config,
)
from app.dependencies import get_current_user, require_roles, get_tenant_scope
from app.schemas.leave_schema import (
    LeaveCreate,
    LeaveOut,
    LeaveWithUserOut,
    LeaveHistoryOut,
    LeaveDisplayOut,
    LeaveNotificationOut,
    LeaveUpdate,
    LeaveBalanceResponse,
)
from app.schemas.leave_config_schema import (
    LeaveAllocationConfigCreate,
    LeaveAllocationConfigOut,
    LeaveAllocationConfigUpdate,
)
from app.db.models.user import User
from app.db.models.leave import Leave
from app.services.office_timing_service import resolve_office_start_time
from fastapi import Body
from app.enums import RoleEnum
from app.utils.department_utils import department_tokens_lower
from app.utils.team_lead_scope import (
    get_team_lead_managed_employee_ids,
    team_lead_can_manage_employee,
)
from app.utils.leave_validation import (
    compute_chargeable_days,
    find_conflicting_leave,
    is_unpaid_leave,
    validate_advance_notice,
    validate_leave_shape,
)

router = APIRouter(prefix="/leave", tags=["Leave"])


def _enforce_leave_business_rules(
    db: Session,
    user: User,
    company_id: int,
    *,
    leave_type: str,
    start_dt: datetime,
    end_dt: datetime,
    duration_days: float,
    leave_session: Optional[str],
    exclude_leave_id: Optional[int] = None,
) -> float:
    """Shared validation for create/update leave. Returns chargeable days."""
    try:
        duration_days, leave_session = validate_leave_shape(
            leave_type=leave_type,
            start_date=start_dt.date(),
            end_date=end_dt.date(),
            duration_days=duration_days,
            leave_session=leave_session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    chargeable_days = compute_chargeable_days(
        start_dt, end_dt, duration_days=duration_days
    )

    if leave_type == "sick" and chargeable_days < 1:
        raise HTTPException(
            status_code=400,
            detail="Sick leave must be for at least 1 day.",
        )

    try:
        validate_advance_notice(
            leave_type=leave_type,
            start_dt=start_dt,
            shift_start_time_resolver=lambda d: _resolve_office_start_time_for_user(
                db, user, company_id
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    conflict = find_conflicting_leave(
        db,
        user_id=user.user_id,
        company_id=company_id,
        start_date=start_dt,
        end_date=end_dt,
        leave_type=leave_type,
        duration_days=duration_days,
        leave_session=leave_session,
        exclude_leave_id=exclude_leave_id,
    )
    if conflict:
        raise HTTPException(
            status_code=400,
            detail=(
                "You have already applied for leave that conflicts on the same date/session "
                "(overlapping leave request detected)."
            ),
        )

    if not is_unpaid_leave(leave_type):
        balances = get_leave_balance(db, user.user_id, company_id=company_id)
        eligible_types = {b["leave_type"] for b in balances}
        if leave_type in eligible_types:
            balance_entry = next(
                (b for b in balances if b["leave_type"] == leave_type),
                None,
            )
            if balance_entry:
                remaining = balance_entry.get("remaining", 0)
                if chargeable_days > remaining:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Not enough remaining {leave_type} leave. "
                            f"Remaining: {remaining}. Requested: {chargeable_days}."
                        ),
                    )

    return chargeable_days

# -------------------------------------------------------------------
# Tenant scoping helpers
# -------------------------------------------------------------------
def _user_scope_filters(scope: dict) -> list:
    """
    Build SQLAlchemy filter clauses to restrict queries to the resolved tenant scope.
    Scope comes from `get_tenant_scope()` and always includes company_id; branch_id may be None.
    """
    clauses = [User.company_id == scope["company_id"]]
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        clauses.append(User.branch_id == branch_id)
    return clauses


def _leave_scope_filters(scope: dict) -> list:
    return [Leave.company_id == int(scope["company_id"])]


def _leave_tenant_filters(scope: dict, user_alias=User) -> list:
    """Filters for leave queries joined to users (company on row, branch on user)."""
    clauses = list(_leave_scope_filters(scope))
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        clauses.append(user_alias.branch_id == int(branch_id))
    return clauses


def _ensure_leave_in_scope(db: Session, leave_id: int, scope: dict) -> Leave:
    leave = (
        db.query(Leave)
        .join(User, Leave.user_id == User.user_id)
        .filter(Leave.leave_id == leave_id, *_leave_tenant_filters(scope))
        .first()
    )
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave not found in this company scope")
    return leave


def _resolve_office_start_time_for_user(
    db: Session,
    user: User,
    company_id: int,
) -> Optional[time]:
    """Department office timing for sick leave; falls back to company default."""
    return resolve_office_start_time(
        db,
        getattr(user, "department", None),
        int(company_id),
    )

# Employee applies for leave
@router.post("/", response_model=LeaveOut)
def request_leave(
    leave: LeaveCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    start_dt = datetime.combine(leave.start_date, datetime.min.time())
    end_dt = datetime.combine(leave.end_date, datetime.min.time())
    leave_type = leave.leave_type.lower()

    if getattr(user, "role", None) == RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin users cannot apply for leave")

    if user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not assigned to a company",
        )
    company_id = int(user.company_id)

    duration_days, leave_session = validate_leave_shape(
        leave_type=leave_type,
        start_date=leave.start_date,
        end_date=leave.end_date,
        duration_days=float(leave.duration_days),
        leave_session=leave.leave_session,
    )
    _enforce_leave_business_rules(
        db,
        user,
        company_id,
        leave_type=leave_type,
        start_dt=start_dt,
        end_dt=end_dt,
        duration_days=duration_days,
        leave_session=leave_session,
    )

    new_leave = apply_leave(
        db,
        user.user_id,
        start_dt,
        end_dt,
        leave.reason,
        leave_type,
        company_id=company_id,
        duration_days=duration_days,
        leave_session=leave_session,
    )
    # Create notifications for appropriate recipients based on department and role
    create_leave_request_notifications(db, new_leave, user)
    return new_leave


# Approve or reject a leave request with role-based validation
@router.put("/{leave_id}/approve", response_model=LeaveOut)
def approve_leave_request(
    leave_id: int,
    approved: bool = Body(default=True, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.TEAM_LEAD, RoleEnum.MANAGER, RoleEnum.HR, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    # Load the leave and requester
    leave = _ensure_leave_in_scope(db, leave_id, scope)

    if leave.status != "Pending":
        raise HTTPException(status_code=400, detail="Only pending leave requests can be approved/rejected")

    requester = (
        db.query(User)
        .filter(User.user_id == leave.user_id, *_user_scope_filters(scope))
        .first()
    )
    if not requester:
        raise HTTPException(status_code=404, detail="Requesting user not found")

    # Prevent self-approval
    if requester.user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="You cannot approve/reject your own leave request")

    requester_role = getattr(requester.role, "value", str(requester.role))

    # Role-based approval rules:
    # - Employee -> TeamLead (same dept + shared project), Manager (same dept), or HR (any dept)
    # - TeamLead -> Manager (same dept) or HR (any dept)
    # - Manager -> Admin or HR (any dept)
    # - HR -> Admin only
    if requester_role == RoleEnum.EMPLOYEE.value:
        if current_user.role not in (RoleEnum.TEAM_LEAD, RoleEnum.MANAGER, RoleEnum.HR):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only TeamLead, Manager or HR can approve/reject this request",
            )
        if current_user.role == RoleEnum.TEAM_LEAD:
            if not team_lead_can_manage_employee(
                db,
                current_user,
                requester,
                company_id=int(scope["company_id"]),
                branch_id=scope.get("branch_id"),
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only approve/reject leave requests from your project team members in your department",
                )
        elif current_user.role == RoleEnum.MANAGER:
            requester_tokens = set(department_tokens_lower(getattr(requester, "department", None)))
            approver_tokens = set(department_tokens_lower(getattr(current_user, "department", None)))
            if not requester_tokens or not approver_tokens or not (requester_tokens & approver_tokens):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only approve/reject requests from your department",
                )
        # HR: company-wide approval for employees (with or without department)
    elif requester_role == RoleEnum.TEAM_LEAD.value:
        if current_user.role not in (RoleEnum.MANAGER, RoleEnum.HR):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Manager or HR can approve/reject this request",
            )
        if current_user.role == RoleEnum.MANAGER:
            requester_tokens = set(department_tokens_lower(getattr(requester, "department", None)))
            approver_tokens = set(department_tokens_lower(getattr(current_user, "department", None)))
            if not requester_tokens or not approver_tokens or not (requester_tokens & approver_tokens):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only approve/reject requests from your department",
                )
        # HR: company-wide approval for team leads (with or without department)
    elif requester_role == RoleEnum.MANAGER.value:
        if current_user.role not in (RoleEnum.ADMIN, RoleEnum.HR):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Admin or HR can approve/reject Manager requests")
    elif requester_role == RoleEnum.HR.value:
        if current_user.role != RoleEnum.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Admin can approve/reject HR requests")
    else:
        # Other roles (including Admin) should not be approvable via this endpoint
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No approver available for this requester role")

    # Apply decision
    if approved:
        updated = approve_leave_db(db, leave_id, company_id=int(scope["company_id"]))
        if not updated:
            raise HTTPException(status_code=404, detail="Leave not found")
        leave = updated
    else:
        leave.status = "Rejected"
        db.commit()
        db.refresh(leave)

    create_leave_decision_notification(db, leave=leave, approver=current_user, approved=approved)
    return leave


# View logged-in user's leave requests
@router.get("/", response_model=list[LeaveDisplayOut])
def view_my_leave(
    period: str = Query(default="all", description="Time period: current_month, last_3_months, last_6_months, last_1_year, custom (with from_date/to_date)"),
    from_date: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Get user's leave history filtered by time period.
    Default: all leaves (when period omitted or blank).
    Options: current_month, last_3_months, last_6_months, last_1_year, custom (with from_date/to_date)
    """
    # Treat blank/empty period as "all"
    if not period or not period.strip():
        period = "all"

    # Parse custom dates if provided
    custom_start = None
    custom_end = None
    
    if from_date or to_date:
        period = "custom"
        if from_date:
            try:
                custom_start = datetime.strptime(from_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
        if to_date:
            try:
                custom_end = datetime.strptime(to_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")
        
        # Validate date order if both are present
        if custom_start and custom_end and custom_start > custom_end:
             raise HTTPException(status_code=400, detail="from_date cannot be after to_date")
             
    if period in ["current_month", "last_3_months", "last_6_months", "last_1_year", "custom"]:
        return list_leave_by_period(
            db,
            user.user_id,
            period,
            custom_start_date=custom_start,
            custom_end_date=custom_end,
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )
    else:
        # Default (all) when period omitted, blank, or invalid
        return list_leave_by_period(
            db,
            user.user_id,
            "all",
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )


@router.get("/balance", response_model=LeaveBalanceResponse)
def leave_balance(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    balances = get_leave_balance(db, user.user_id, company_id=int(scope["company_id"]))
    return {"balances": balances}


@router.put("/{leave_id}", response_model=LeaveOut)
def update_leave_request(
    leave_id: int,
    leave_update: LeaveUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    # Get the existing leave to check its type
    existing_leave = (
        db.query(Leave)
        .filter(
            Leave.leave_id == leave_id,
            Leave.user_id == user.user_id,
            Leave.company_id == int(scope["company_id"]),
        )
        .first()
    )
    if not existing_leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    if existing_leave.status != "Pending":
        raise HTTPException(status_code=400, detail="Only pending leave requests can be updated")
    
    start_date = None
    end_date = None
    leave_type = None
    if leave_update.start_date:
        start_date = datetime.combine(leave_update.start_date, datetime.min.time())
    if leave_update.end_date:
        end_date = datetime.combine(leave_update.end_date, datetime.min.time())
    if leave_update.leave_type:
        leave_type = leave_update.leave_type.lower()

    final_start_date = start_date or existing_leave.start_date
    final_end_date = end_date or existing_leave.end_date
    final_leave_type = leave_type or (existing_leave.leave_type or "annual").lower()

    existing_duration = float(existing_leave.duration_days or 1.0)
    final_duration = (
        float(leave_update.duration_days)
        if leave_update.duration_days is not None
        else existing_duration
    )
    if leave_update.leave_session is not None:
        final_session = leave_update.leave_session
    elif leave_update.duration_days is not None and float(leave_update.duration_days) == 1.0:
        final_session = None
    else:
        final_session = existing_leave.leave_session

    duration_days, leave_session = validate_leave_shape(
        leave_type=final_leave_type,
        start_date=final_start_date.date(),
        end_date=final_end_date.date(),
        duration_days=final_duration,
        leave_session=final_session,
    )
    _enforce_leave_business_rules(
        db,
        user,
        int(scope["company_id"]),
        leave_type=final_leave_type,
        start_dt=final_start_date,
        end_dt=final_end_date,
        duration_days=duration_days,
        leave_session=leave_session,
        exclude_leave_id=leave_id,
    )

    updated_leave = update_leave_db(
        db,
        leave_id,
        user.user_id,
        start_date=start_date,
        end_date=end_date,
        reason=leave_update.reason,
        leave_type=leave_type,
        company_id=int(scope["company_id"]),
        duration_days=duration_days,
        leave_session=leave_session,
        clear_leave_session=leave_session is None,
    )

    if updated_leave is None:
        raise HTTPException(status_code=404, detail="Leave not found")
    if updated_leave == "not_pending":
        raise HTTPException(status_code=400, detail="Only pending leave requests can be updated")

    # Update existing approver notifications for this leave_id (same recipients)
    update_leave_request_notifications(db, updated_leave, user)
    return updated_leave


@router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_leave_request(
    leave_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    result = delete_leave_db(db, leave_id, user.user_id, company_id=int(scope["company_id"]))
    if result is None:
        raise HTTPException(status_code=404, detail="Leave not found")
    if result == "not_pending":
        raise HTTPException(status_code=400, detail="Only pending leave requests can be deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Approvals inbox for approvers based on hierarchy
@router.get("/approvals", response_model=list[LeaveHistoryOut])
def approvals_inbox(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Pending approvals visibility:
    - ADMIN: pending requests from HR and Managers.
    - HR (with or without department): pending requests from Managers, Team Leads, and Employees (all departments).
    - MANAGER (with one or many departments): pending requests from Team Leads and Employees
      whose department list intersects with the manager's department(s).
    - TEAM_LEAD: pending requests from Employees who share the same department(s)
      AND an active project where the TeamLead is also an active member (not self).
    - Other roles: no approvals inbox (empty list).
    """
    role_value = getattr(user.role, "value", str(user.role))

    if role_value == RoleEnum.ADMIN.value:
        # Admin sees only HR/Manager requests
        pending = list_pending_by_requester_roles(
            db,
            [RoleEnum.HR.value, RoleEnum.MANAGER.value],
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )
    elif role_value == RoleEnum.HR.value:
        # HR sees all pending requests from Managers, Team Leads, and Employees (any department)
        pending = list_pending_by_requester_roles(
            db,
            [RoleEnum.MANAGER.value, RoleEnum.TEAM_LEAD.value, RoleEnum.EMPLOYEE.value],
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )
    elif role_value == RoleEnum.MANAGER.value:
        # Managers see Team Lead / Employee requests from their own department(s)
        manager_tokens = set(department_tokens_lower(user.department))
        if not manager_tokens:
            return []

        all_pending = list_pending_by_requester_roles(
            db,
            [RoleEnum.TEAM_LEAD.value, RoleEnum.EMPLOYEE.value],
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )
        pending = []
        for leave in all_pending:
            u: User = leave.user
            if not u or not u.department:
                continue
            requester_tokens = set(department_tokens_lower(u.department))
            if manager_tokens.intersection(requester_tokens):
                pending.append(leave)
    elif role_value == RoleEnum.TEAM_LEAD.value:
        managed_employee_ids = get_team_lead_managed_employee_ids(
            db,
            user,
            company_id=int(scope["company_id"]),
            branch_id=scope.get("branch_id"),
        )

        all_pending_employees = list_pending_by_requester_roles(
            db,
            [RoleEnum.EMPLOYEE.value],
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )
        pending = [
            leave
            for leave in all_pending_employees
            if leave.user_id in managed_employee_ids
        ]
    else:
        return []

    # Enrich with user details
    results = []
    for leave in pending:
        u: User = leave.user
        results.append({
            "leave_id": leave.leave_id,
            "company_id": int(leave.company_id),
            "user_id": leave.user_id,
            "start_date": leave.start_date.date(),
            "end_date": leave.end_date.date(),
            "reason": leave.reason,
            "status": leave.status,
            "leave_type": (leave.leave_type or "annual").lower(),
            "type": (leave.leave_type or "annual").lower(),
            "employee_id": u.employee_id if u else "",
            "name": u.name if u else "",
            "department": u.department if u else None,
            "role": getattr(u.role, "value", str(u.role)) if u and u.role else None,
        })
    return results


# Approver's decision history
@router.get("/approvals/history", response_model=list[LeaveHistoryOut])
def approvals_history(
    date_range: Optional[Literal["current_month", "last_month", "last_3_months", "last_6_months", "last_1_year", "custom"]] = Query(None, description="Filter by date range"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD) for custom range"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD) for custom range"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Return decided (non-pending) leave decisions visible to the current user:
    - ADMIN: all users except Admins and self.
    - HR: all users except Admins, HRs, and self.
    - MANAGER: users in their department(s), excluding Admins, HRs, other Managers, and self.
    - TEAM_LEAD: decided leaves from Employees in same department(s) who share
      an active project with the TeamLead (not self).
    - EMPLOYEE: their own decided leaves.
    
    Supports filtering by date range:
    - current_month: First day of current month to end of current month
    - last_month: First day of last month to last day of last month
    - last_3_months: 3 months ago from start of current month
    - last_6_months: 6 months ago from start of current month
    - last_1_year: 1 year ago from start of current month
    - custom: Requires start_date and end_date parameters
    """
    role_value = getattr(user.role, "value", str(user.role))

    # Base query for decided leaves
    base_query = (
        db.query(Leave)
        .options(joinedload(Leave.user))
        .join(User, Leave.user_id == User.user_id)
        .filter(Leave.status != "Pending", *_leave_tenant_filters(scope))
    )

    if role_value == RoleEnum.ADMIN.value:
        # Admin: all users except Admins and self
        decided = (
            base_query
            .filter(User.role != RoleEnum.ADMIN)
            .filter(User.user_id != user.user_id)
            .order_by(Leave.end_date.desc())
            .all()
        )
    elif role_value == RoleEnum.HR.value:
        # HR: all users except Admins, HRs, and self
        decided = (
            base_query
            .filter(User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]))
            .filter(User.user_id != user.user_id)
            .order_by(Leave.end_date.desc())
            .all()
        )
    elif role_value == RoleEnum.MANAGER.value:
        # Manager: users in own department(s), excluding Admins, HRs, other Managers, and self.
        if not user.department:
            return []
        manager_tokens = set(department_tokens_lower(user.department))
        if not manager_tokens:
            return []

        # Fetch candidate decided leaves for non-privileged roles, then apply token overlap filter.
        candidates = (
            base_query
            .filter(User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]))
            .filter(User.user_id != user.user_id)
            .order_by(Leave.end_date.desc())
            .all()
        )

        decided = []
        for leave in candidates:
            u: User = leave.user
            requester_tokens = set(department_tokens_lower(getattr(u, "department", None)))
            if requester_tokens and manager_tokens.intersection(requester_tokens):
                decided.append(leave)
    elif role_value == RoleEnum.TEAM_LEAD.value:
        managed_employee_ids = get_team_lead_managed_employee_ids(
            db,
            user,
            company_id=int(scope["company_id"]),
            branch_id=scope.get("branch_id"),
        )

        if not managed_employee_ids:
            decided = []
        else:
            decided = (
                base_query
                .filter(User.role == RoleEnum.EMPLOYEE)
                .filter(User.user_id.in_(managed_employee_ids))
                .order_by(Leave.end_date.desc())
                .all()
            )
    elif role_value == RoleEnum.EMPLOYEE.value:
        # Employees see only their own decided leaves
        decided = base_query.filter(Leave.user_id == user.user_id).order_by(Leave.end_date.desc()).all()
    else:
        # Other roles: no access
        return []

    results: list[dict] = []
    for leave in decided:
        u: User = leave.user
        results.append({
            "leave_id": leave.leave_id,
            "company_id": int(leave.company_id),
            "user_id": leave.user_id,
            "start_date": leave.start_date.date(),
            "end_date": leave.end_date.date(),
            "reason": leave.reason,
            "status": leave.status,
            "leave_type": (leave.leave_type or "annual").lower(),
            "type": (leave.leave_type or "annual").lower(),
            "employee_id": u.employee_id if u else "",
            "name": u.name if u else "",
            "department": u.department if u else None,
            "role": getattr(u.role, "value", str(u.role)) if u and u.role else None,
        })
    
    # Apply date range filter if provided
    if date_range:
        now = now_ist()
        date_start = None
        date_end = None
        
        if date_range == "current_month":
            # First day of current month to end of current month
            date_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                date_end = now.replace(year=now.year + 1, month=1, day=1, hour=23, minute=59, second=59, microsecond=999999) - timedelta(days=1)
            else:
                date_end = (now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        elif date_range == "last_month":
            # First day of last month to last day of last month
            if now.month == 1:
                date_start = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
                date_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            else:
                date_start = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)
                date_end = (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        elif date_range == "last_3_months":
            # 3 months ago from start of current month
            date_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Calculate 3 months back
            months_back = 3
            year = now.year
            month = now.month
            for _ in range(months_back):
                month -= 1
                if month == 0:
                    month = 12
                    year -= 1
            date_start = now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif date_range == "last_6_months":
            # 6 months ago from start of current month
            date_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Calculate 6 months back
            months_back = 6
            year = now.year
            month = now.month
            for _ in range(months_back):
                month -= 1
                if month == 0:
                    month = 12
                    year -= 1
            date_start = now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif date_range == "last_1_year":
            # 1 year ago from start of current month
            date_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            date_start = now.replace(year=now.year - 1, month=now.month, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif date_range == "custom":
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date and end_date are required when date_range is 'custom'"
                )
            try:
                date_start = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
                date_end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )
        
        # Filter results by date range (using start_date of the leave)
        if date_start and date_end:
            results = [
                result for result in results
                if result.get("start_date") and date_start.date() <= result["start_date"] <= date_end.date()
            ]
    
    return results


# Leave notifications endpoints
@router.get("/notifications", response_model=list[LeaveNotificationOut])
def get_leave_notifications(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Get leave notifications for the current user (scoped for TeamLeads)."""
    notifications = list_leave_notifications(
        db,
        user.user_id,
        viewer=user,
        company_id=int(scope["company_id"]),
        branch_id=scope.get("branch_id"),
    )
    return notifications


@router.put("/notifications/{notification_id}/read", response_model=LeaveNotificationOut)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Mark a leave notification as read."""
    notification = mark_leave_notification_as_read(
        db,
        notification_id,
        user.user_id,
        viewer=user,
        company_id=int(scope["company_id"]),
        branch_id=scope.get("branch_id"),
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


# ============================================================================
# LEAVE ALLOCATION CONFIGURATION ENDPOINTS (Admin Only)
# ============================================================================

@router.get("/config/allocation", response_model=LeaveAllocationConfigOut)
def get_leave_allocation_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Get the active leave allocation configuration for the current tenant company.
    Only accessible by admins.
    """
    config = get_active_leave_config(db, int(scope["company_id"]))
    
    if not config:
        # Return default configuration if none exists
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No leave allocation configuration found. Please create one."
        )
    
    return config


@router.post("/config/allocation", response_model=LeaveAllocationConfigOut, status_code=status.HTTP_201_CREATED)
def create_leave_allocation_config_route(
    config_data: LeaveAllocationConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Create a new leave allocation configuration for the current tenant company.
    Deactivates previous configurations for that company only.
    Only accessible by admins.
    """
    sick = config_data.sick_leave_allocation
    casual = config_data.casual_leave_allocation
    other = config_data.other_leave_allocation

    # total_annual_leave is derived as sick + casual
    total = sick + casual
    if total < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Annual leave must be at least 1 day (derived as sick + casual)",
        )
    
    # Create the configuration
    config = create_leave_config(
        db=db,
        company_id=int(scope["company_id"]),
        total_annual_leave=total,
        sick_leave_allocation=sick,
        casual_leave_allocation=casual,
        other_leave_allocation=other,
        updated_by=current_user.user_id,
    )
    
    return config


@router.put("/config/allocation/{config_id}", response_model=LeaveAllocationConfigOut)
def update_leave_allocation_config_route(
    config_id: int,
    config_data: LeaveAllocationConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Update an existing leave allocation configuration for the current tenant company.
    Only accessible by admins.
    """
    config = update_leave_config(
        db=db,
        config_id=config_id,
        company_id=int(scope["company_id"]),
        sick_leave_allocation=config_data.sick_leave_allocation,
        casual_leave_allocation=config_data.casual_leave_allocation,
        other_leave_allocation=config_data.other_leave_allocation,
        updated_by=current_user.user_id,
    )
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave allocation configuration not found"
        )
    
    return config


@router.get("/config/allocation/current")
def get_current_leave_allocation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Get the current leave allocation values for the tenant company.
    Returns default values if no configuration exists.
    Note: annual_leave = sick_leave_allocation + casual_leave_allocation
    """
    config = get_active_leave_config(db, int(scope["company_id"]))
    
    if config:
        # Calculate annual as sick + casual
        annual_calculated = config.sick_leave_allocation + config.casual_leave_allocation
        return {
            "total_annual_leave": annual_calculated,  # Calculated as sick + casual
            "sick_leave_allocation": config.sick_leave_allocation,
            "casual_leave_allocation": config.casual_leave_allocation,
            "other_leave_allocation": config.other_leave_allocation,
            "is_configured": True
        }
    
    # Return defaults (annual = sick + casual = 10 + 5 = 15)
    return {
        "total_annual_leave": 15,  # Calculated as sick (10) + casual (5)
        "sick_leave_allocation": 10,
        "casual_leave_allocation": 5,
        "other_leave_allocation": 0,
        "is_configured": False
    }
