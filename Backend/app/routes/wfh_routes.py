"""
Work From Home (WFH) Request Routes
API endpoints for WFH request management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time, date
from typing import Optional, Literal

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.wfh_request import WFHRequest, WFHStatus
from app.dependencies import get_current_user, get_tenant_scope, require_roles
from app.enums import RoleEnum
from app.utils.timezone import now_ist
from app.utils.department_utils import department_tokens_lower
from app.utils.team_lead_scope import team_lead_can_manage_employee

from app.schemas.wfh_schema import (
    WFHRequestCreate,
    WFHRequestOut,
    WFHRequestWithUserOut,
    WFHRequestApprove,
    WFHRequestUpdate,
    WFHRequestListResponse,
    WFHNotificationOut,
)
from app.crud.wfh_crud import (
    create_wfh_request,
    get_wfh_request_by_id,
    get_user_wfh_requests,
    get_all_wfh_requests,
    approve_wfh_request,
    update_wfh_request,
    delete_wfh_request,
    check_overlapping_wfh,
    get_pending_wfh_count_for_user,
    create_wfh_request_notifications,
    update_wfh_request_notifications,
    create_wfh_decision_notification,
    create_wfh_deletion_notification,
    list_wfh_notifications,
    mark_wfh_notification_as_read,
)


router = APIRouter(prefix="/wfh", tags=["Work From Home"])

def _user_scope_filters(scope: dict, user_alias=User) -> list:
    clauses = [user_alias.company_id == scope["company_id"]]
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        clauses.append(user_alias.branch_id == branch_id)
    return clauses


def _get_user_in_scope(db: Session, *, user_id: int, scope: dict) -> User | None:
    return (
        db.query(User)
        .filter(User.user_id == user_id, User.is_active.is_(True), *_user_scope_filters(scope))
        .first()
    )


def _assert_current_in_scope(db: Session, *, current_user: User, scope: dict) -> None:
    # Admin tenant scope is assignment-based and validated by get_tenant_scope.
    if current_user.role == RoleEnum.ADMIN:
        return
    if _get_user_in_scope(db, user_id=int(current_user.user_id), scope=scope) is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current user is outside selected tenant scope")


def _can_approver_handle_target(
    approver: User,
    target: User,
    *,
    db: Optional[Session] = None,
    company_id: Optional[int] = None,
    branch_id: Optional[int] = None,
) -> bool:
    """
    Determine whether `approver` is allowed to approve/reject `target`'s WFH request
    according to the role-based hierarchy rules:
      - Admins can approve HRs and Managers
      - HRs can approve Managers, TeamLead, and Employees
      - Managers can approve TeamLead and Employees, but only for departments they manage
      - TeamLeads can approve Employees in same department(s) who share an active project
    """
    # Admin: can approve HRs and Managers
    if approver.role == RoleEnum.ADMIN:
        return target.role in (RoleEnum.HR, RoleEnum.MANAGER)

    # HR: can approve Managers, TeamLead, Employees
    if approver.role == RoleEnum.HR:
        return target.role in (RoleEnum.MANAGER, RoleEnum.TEAM_LEAD, RoleEnum.EMPLOYEE)

    # Manager: can approve TeamLead and Employee within overlapping departments
    if approver.role == RoleEnum.MANAGER:
        if target.role not in (RoleEnum.TEAM_LEAD, RoleEnum.EMPLOYEE):
            return False
        approver_tokens = set(department_tokens_lower(approver.department))
        target_tokens = set(department_tokens_lower(target.department))
        return bool(approver_tokens.intersection(target_tokens))

    # TeamLead: same department + shared active project membership
    if approver.role == RoleEnum.TEAM_LEAD:
        if target.role != RoleEnum.EMPLOYEE or db is None or company_id is None:
            return False
        return team_lead_can_manage_employee(
            db,
            approver,
            target,
            company_id=int(company_id),
            branch_id=branch_id,
        )

    # Default: no permission
    return False


# ============================================
# Employee Endpoints (All authenticated users)
# ============================================

@router.post("/request", response_model=WFHRequestOut, status_code=status.HTTP_201_CREATED)
def submit_wfh_request(
    payload: WFHRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Submit a Work From Home request.
    
    Requirements:
    - Valid start and end dates
    - Reason (10-500 characters)
    - Must be submitted at least 24 hours in advance (for dates in the future)
    - No overlapping WFH requests
    """
    # Convert dates to datetime
    # Prevent Admins from submitting WFH requests
    if current_user.role == RoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins are not permitted to submit WFH requests"
        )
    
    _assert_current_in_scope(db, current_user=current_user, scope=scope)

    start_dt = datetime.combine(payload.start_date, time.min)
    # Use 23:59:59 with no microseconds to avoid DB rounding into next day (00:00:00)
    end_dt = datetime.combine(payload.end_date, time(23, 59, 59))
    
    # Validation: must be at least 24 hours in the future (no today or past dates)
    now = now_ist()
    time_difference = start_dt - now
    hours_difference = time_difference.total_seconds() / 3600
    if hours_difference < 24:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WFH requests must be submitted at least 24 hours in advance and cannot start today or in the past.",
        )
    
    # Check for overlapping requests
    if check_overlapping_wfh(
        db,
        current_user.user_id,
        start_dt,
        end_dt,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a pending or approved WFH request for the selected dates."
        )
    
    # Create the request
    wfh_request = create_wfh_request(
        db=db,
        user_id=current_user.user_id,
        start_date=start_dt,
        end_date=end_dt,
        reason=payload.reason,
        wfh_type=payload.wfh_type,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    create_wfh_request_notifications(db, wfh_request, current_user)
    
    return WFHRequestOut(
        wfh_id=wfh_request.wfh_id,
        user_id=wfh_request.user_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        wfh_type=wfh_request.wfh_type,
        reason=wfh_request.reason,
        status=wfh_request.status,
        approved_by=wfh_request.approved_by,
        approved_at=wfh_request.approved_at,
        rejection_reason=wfh_request.rejection_reason,
        created_at=wfh_request.created_at,
        updated_at=wfh_request.updated_at
    )


@router.get("/my-requests", response_model=list[WFHRequestOut])
def get_my_wfh_requests(
    status_filter: Optional[str] = Query(None, description="Filter by status: Pending, Approved, Rejected"),
    date_range: Optional[Literal["current_month", "last_month", "last_3_months", "last_6_months", "last_1_year", "custom"]] = Query(None, description="Filter by date range"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD) for custom range"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD) for custom range"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Get all WFH requests submitted by the current user.
    Supports filtering by status and date range.
    """
    _assert_current_in_scope(db, current_user=current_user, scope=scope)
    requests = get_user_wfh_requests(
        db,
        current_user.user_id,
        status_filter,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
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
        
        # Filter requests by date range (using start_date of the WFH request)
        if date_start and date_end:
            requests = [
                req for req in requests
                if req.start_date and date_start <= req.start_date <= date_end
            ]
    
    return [
        WFHRequestOut(
            wfh_id=req.wfh_id,
            user_id=req.user_id,
            start_date=req.start_date.date() if req.start_date else None,
            end_date=req.end_date.date() if req.end_date else None,
            wfh_type=req.wfh_type,
            reason=req.reason,
            status=req.status,
            approved_by=req.approved_by,
            approved_at=req.approved_at,
            rejection_reason=req.rejection_reason,
            created_at=req.created_at,
            updated_at=req.updated_at
        )
        for req in requests
    ]


@router.get("/my-requests/{wfh_id}", response_model=WFHRequestOut)
def get_my_wfh_request_detail(
    wfh_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Get details of a specific WFH request submitted by the current user.
    """
    _assert_current_in_scope(db, current_user=current_user, scope=scope)
    wfh_request = get_wfh_request_by_id(
        db,
        wfh_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
    if not wfh_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WFH request not found"
        )
    
    if wfh_request.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own WFH requests"
        )
    
    return WFHRequestOut(
        wfh_id=wfh_request.wfh_id,
        user_id=wfh_request.user_id,
        start_date=wfh_request.start_date.date() if wfh_request.start_date else None,
        end_date=wfh_request.end_date.date() if wfh_request.end_date else None,
        wfh_type=wfh_request.wfh_type,
        reason=wfh_request.reason,
        status=wfh_request.status,
        approved_by=wfh_request.approved_by,
        approved_at=wfh_request.approved_at,
        rejection_reason=wfh_request.rejection_reason,
        created_at=wfh_request.created_at,
        updated_at=wfh_request.updated_at
    )


@router.put("/my-requests/{wfh_id}", response_model=WFHRequestOut)
def update_my_wfh_request(
    wfh_id: int,
    payload: WFHRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Update a pending WFH request (only the owner can update).
    """
    _assert_current_in_scope(db, current_user=current_user, scope=scope)
    wfh_request = get_wfh_request_by_id(
        db,
        wfh_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
    if not wfh_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WFH request not found"
        )
    
    if wfh_request.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own WFH requests"
        )
    
    if wfh_request.status != WFHStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be updated"
        )
    
    # Convert dates if provided
    start_dt = datetime.combine(payload.start_date, time.min) if payload.start_date else None
    # Use 23:59:59 with no microseconds to avoid DB rounding into next day (00:00:00)
    end_dt = datetime.combine(payload.end_date, time(23, 59, 59)) if payload.end_date else None
    
    # Validation: if start date is being updated, it must be at least 24 hours in the future
    if start_dt:
        now = now_ist()
        time_difference = start_dt - now
        hours_difference = time_difference.total_seconds() / 3600
        if hours_difference < 24:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Updated WFH start date must be at least 24 hours in advance and cannot be today or in the past.",
            )

    # Check for overlapping requests if dates are being updated
    if start_dt or end_dt:
        check_start = start_dt or wfh_request.start_date
        check_end = end_dt or wfh_request.end_date
        
        if check_overlapping_wfh(
            db,
            current_user.user_id,
            check_start,
            check_end,
            exclude_wfh_id=wfh_id,
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The updated dates overlap with another pending or approved WFH request."
            )
    
    updated = update_wfh_request(
        db=db,
        wfh_id=wfh_id,
        user_id=current_user.user_id,
        start_date=start_dt,
        end_date=end_dt,
        wfh_type=payload.wfh_type,
        reason=payload.reason,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update WFH request"
        )
    update_wfh_request_notifications(db, updated, current_user)
    
    return WFHRequestOut(
        wfh_id=updated.wfh_id,
        user_id=updated.user_id,
        start_date=updated.start_date.date() if updated.start_date else None,
        end_date=updated.end_date.date() if updated.end_date else None,
        wfh_type=updated.wfh_type,
        reason=updated.reason,
        status=updated.status,
        approved_by=updated.approved_by,
        approved_at=updated.approved_at,
        rejection_reason=updated.rejection_reason,
        created_at=updated.created_at,
        updated_at=updated.updated_at
    )


@router.delete("/my-requests/{wfh_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_wfh_request(
    wfh_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Delete a pending WFH request (only the owner can delete).
    """
    _assert_current_in_scope(db, current_user=current_user, scope=scope)
    wfh_request = get_wfh_request_by_id(
        db,
        wfh_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
    if not wfh_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WFH request not found"
        )
    
    if wfh_request.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own WFH requests"
        )
    
    if wfh_request.status != WFHStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be deleted"
        )
    create_wfh_deletion_notification(
        db,
        wfh_request,
        current_user,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    deleted = delete_wfh_request(
        db,
        wfh_id,
        current_user.user_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete WFH request"
        )
    
    return None


# ============================================
# Manager/HR/Admin Endpoints
# ============================================

@router.get("/requests", response_model=WFHRequestListResponse)
def get_all_requests(
    status_filter: Optional[str] = Query(None, description="Filter by status: Pending, Approved, Rejected"),
    department: Optional[str] = Query(None, description="Filter by department"),
    date_range: Optional[Literal["current_month", "last_month", "last_3_months", "last_6_months", "last_1_year", "custom"]] = Query(None, description="Filter by date range"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD) for custom range"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD) for custom range"),
    role_filter: Optional[Literal["ADMIN", "HR", "MANAGER", "TEAM_LEAD", "EMPLOYEE"]] = Query(None, description="Filter by requester role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.TEAM_LEAD, RoleEnum.MANAGER, RoleEnum.HR, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Get all WFH requests (for TeamLead/Manager/HR/Admin).
    
    Role-based hierarchy validation:
    - Admin: Can see all requests except Admins and self
    - HR: Can see all requests except Admins, HRs, and self
    - Manager: Can see requests from their department(s) only, excluding Admins, HRs, Managers, and self
    - TeamLead: Can see Employee requests from same department(s) who share an active
      project with the TeamLead, excluding self
    
    Supports filtering by status, department, date range, and role.
    """
    requests, pending_count = get_all_wfh_requests(
        db=db,
        status_filter=status_filter,
        department_filter=department,
        requester_user=current_user,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
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
            # 3 months ago from start of current month to end of last month
            date_end = (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
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
            # 6 months ago from start of current month to end of last month
            date_end = (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
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
            # 1 year ago from start of current month to end of last month
            date_end = (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
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
        
        # Filter requests by date range (using start_date of the WFH request)
        if date_start and date_end:
            filtered_requests = []
            for req in requests:
                if req.get("start_date"):
                    # req["start_date"] is already a date object, convert to datetime for comparison
                    req_start_dt = datetime.combine(req["start_date"], time.min)
                    if date_start <= req_start_dt <= date_end:
                        filtered_requests.append(req)
            requests = filtered_requests
    
    # Apply role filter if provided
    if role_filter:
        # Map filter values to actual RoleEnum values (case-sensitive)
        role_filter_map = {
            "ADMIN": "Admin",
            "HR": "HR",
            "MANAGER": "Manager",
            "TEAM_LEAD": "TeamLead",
            "EMPLOYEE": "Employee"
        }
        actual_role_value = role_filter_map.get(role_filter)
        if actual_role_value:
            # If the requested role isn't visible under the current user's hierarchy,
            # return a clear 403 instead of an empty list.
            if current_user.role == RoleEnum.ADMIN and actual_role_value == RoleEnum.ADMIN.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins cannot view Admin WFH requests via this endpoint",
                )
            if current_user.role == RoleEnum.HR and actual_role_value in {RoleEnum.ADMIN.value, RoleEnum.HR.value}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="HR cannot view Admin/HR WFH requests via this endpoint",
                )
            if current_user.role == RoleEnum.MANAGER and actual_role_value in {RoleEnum.ADMIN.value, RoleEnum.HR.value, RoleEnum.MANAGER.value}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Managers cannot view Admin/HR/Manager WFH requests via this endpoint",
                )
            if current_user.role == RoleEnum.TEAM_LEAD and actual_role_value in {RoleEnum.ADMIN.value, RoleEnum.HR.value, RoleEnum.MANAGER.value, RoleEnum.TEAM_LEAD.value}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="TeamLeads can only view Employee WFH requests via this endpoint",
                )

            requests = [req for req in requests if req.get("role") == actual_role_value]
    
    return WFHRequestListResponse(
        total=len(requests),
        pending_count=pending_count,
        requests=[
            WFHRequestWithUserOut(**req)
            for req in requests
        ]
    )


@router.get("/requests/{wfh_id}", response_model=WFHRequestWithUserOut)
def get_request_detail(
    wfh_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.TEAM_LEAD, RoleEnum.MANAGER, RoleEnum.HR, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Get details of a specific WFH request (for TeamLead/Manager/HR/Admin).
    """
    wfh_request = get_wfh_request_by_id(
        db,
        wfh_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
    if not wfh_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WFH request not found"
        )
    
    # Get user details
    user = _get_user_in_scope(db, user_id=int(wfh_request.user_id), scope=scope)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Role-based hierarchy validation (match /wfh/requests list rules)
    # - Admin: cannot view Admin requests or self
    # - HR: cannot view Admin/HR requests or self
    # - Manager: cannot view Admin/HR/Manager requests or self; must be within managed department(s)
    if current_user.user_id == user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot view your own WFH request via this endpoint",
        )

    if current_user.role == RoleEnum.ADMIN:
        if user.role == RoleEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot view Admin WFH requests via this endpoint",
            )

    elif current_user.role == RoleEnum.HR:
        if user.role in (RoleEnum.ADMIN, RoleEnum.HR):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HR cannot view Admin/HR WFH requests via this endpoint",
            )
    
    # Manager can only see requests from their department(s)
    if current_user.role == RoleEnum.MANAGER:
        # Managers cannot view Admin/HR/Manager requests (defensive check)
        if user.role in (RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers cannot view Admin/HR/Manager WFH requests via this endpoint",
            )
        if not _can_approver_handle_target(
            current_user,
            user,
            db=db,
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view requests from your department(s)"
            )

    # TeamLead can only see managed project team Employee requests
    if current_user.role == RoleEnum.TEAM_LEAD:
        if user.role != RoleEnum.EMPLOYEE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="TeamLeads can only view Employee WFH requests via this endpoint",
            )
        if not _can_approver_handle_target(
            current_user,
            user,
            db=db,
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view WFH requests from your project team members in your department",
            )
    
    # Get approver name if exists
    approver_name = None
    if wfh_request.approved_by:
        approver = db.query(User.name).filter(User.user_id == wfh_request.approved_by).scalar()
        approver_name = approver
    
    return WFHRequestWithUserOut(
        wfh_id=wfh_request.wfh_id,
        user_id=wfh_request.user_id,
        employee_id=user.employee_id,
        name=user.name,
        department=user.department,
        role=user.role.value if user.role else None,
        start_date=wfh_request.start_date.date() if wfh_request.start_date else None,
        end_date=wfh_request.end_date.date() if wfh_request.end_date else None,
        wfh_type=wfh_request.wfh_type,
        reason=wfh_request.reason,
        status=wfh_request.status,
        approved_by=wfh_request.approved_by,
        approver_name=approver_name,
        approved_at=wfh_request.approved_at,
        rejection_reason=wfh_request.rejection_reason,
        created_at=wfh_request.created_at,
        updated_at=wfh_request.updated_at
    )


@router.put("/requests/{wfh_id}/approve", response_model=WFHRequestWithUserOut)
def approve_or_reject_request(
    wfh_id: int,
    payload: WFHRequestApprove,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.TEAM_LEAD, RoleEnum.MANAGER, RoleEnum.HR, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Approve or reject a WFH request (for TeamLead/Manager/HR/Admin).
    
    - Manager: Can approve/reject requests from their department only
    - TeamLead: Can approve/reject Employee requests from shared project + department
    - HR/Admin: Can approve/reject all requests
    """
    wfh_request = get_wfh_request_by_id(
        db,
        wfh_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
    if not wfh_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WFH request not found"
        )
    
    if wfh_request.status != WFHStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {wfh_request.status.lower()}"
        )
    
    # Get user to check department
    user = _get_user_in_scope(db, user_id=int(wfh_request.user_id), scope=scope)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request user not found"
        )
    
    # Enforce role-hierarchy approval rules for all approvers
    if not _can_approver_handle_target(
        current_user,
        user,
        db=db,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not permitted to approve/reject this user's WFH request according to role hierarchy",
        )
    
    # Prevent self-approval
    if wfh_request.user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot approve/reject your own WFH request"
        )
    
    # Approve or reject
    updated = approve_wfh_request(
        db=db,
        wfh_id=wfh_id,
        approver_id=current_user.user_id,
        approved=payload.approved,
        rejection_reason=payload.rejection_reason,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to process the request"
        )
    create_wfh_decision_notification(
        db,
        wfh_request=updated,
        approver=current_user,
        approved=payload.approved,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
    return WFHRequestWithUserOut(
        wfh_id=updated.wfh_id,
        user_id=updated.user_id,
        employee_id=user.employee_id,
        name=user.name,
        department=user.department,
        role=user.role.value if user.role else None,
        start_date=updated.start_date.date() if updated.start_date else None,
        end_date=updated.end_date.date() if updated.end_date else None,
        wfh_type=updated.wfh_type,
        reason=updated.reason,
        status=updated.status,
        approved_by=updated.approved_by,
        approver_name=current_user.name,
        approved_at=updated.approved_at,
        rejection_reason=updated.rejection_reason,
        created_at=updated.created_at,
        updated_at=updated.updated_at
    )


@router.get("/pending-count")
def get_pending_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.TEAM_LEAD, RoleEnum.MANAGER, RoleEnum.HR, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Get count of pending WFH requests (for TeamLead/Manager/HR/Admin).
    Useful for showing notification badges.
    """
    # Tenant scoping is applied in /wfh/requests; for pending-count keep consistent by reusing that view.
    # (Counts visible pending requests within selected tenant scope.)
    _, pending_count = get_all_wfh_requests(
        db=db,
        status_filter=None,
        department_filter=None,
        requester_user=current_user,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    count = pending_count
    return {"pending_count": count}


@router.get("/notifications", response_model=list[WFHNotificationOut])
def get_wfh_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Get WFH notifications for the current user (scoped for TeamLeads)."""
    _assert_current_in_scope(db, current_user=current_user, scope=scope)
    return list_wfh_notifications(
        db,
        current_user.user_id,
        viewer=current_user,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )


@router.put("/notifications/{notification_id}/read", response_model=WFHNotificationOut)
def read_wfh_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Mark a WFH notification as read."""
    _assert_current_in_scope(db, current_user=current_user, scope=scope)
    notification = mark_wfh_notification_as_read(
        db,
        notification_id,
        current_user.user_id,
        viewer=current_user,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification

