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
from app.dependencies import get_current_user, require_roles
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
from fastapi import Body
from app.enums import RoleEnum

router = APIRouter(prefix="/leave", tags=["Leave"])

# Employee applies for leave
@router.post("/", response_model=LeaveOut)
def request_leave(
    leave: LeaveCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    start_dt = datetime.combine(leave.start_date, datetime.min.time())
    end_dt = datetime.combine(leave.end_date, datetime.min.time())
    
    # Calculate leave duration
    leave_days = (end_dt - start_dt).days + 1
    
    # Validation 0: Admins cannot apply for leave
    if getattr(user, "role", None) == RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin users cannot apply for leave")
    
    # Validation 1: Sick leave minimum duration (1 day)
    if leave.leave_type.lower() == 'sick' and leave_days < 1:
        raise HTTPException(
            status_code=400,
            detail="Sick leave must be for at least 1 day."
        )
    
    # Validation 2: Advance notice requirements
    now = now_ist()
    time_difference = start_dt - now
    hours_difference = time_difference.total_seconds() / 3600
    
    if leave.leave_type.lower() == 'sick':
        # Sick leave: cannot be for past dates; cannot be for future dates beyond 24 hrs; reject if within 2 hrs of start
        if hours_difference < 0:
            raise HTTPException(
                status_code=400,
                detail="Sick leave cannot be applied for past dates."
            )
        if hours_difference > 24:
            raise HTTPException(
                status_code=400,
                detail="Sick leave cannot be applied for future dates. It must be applied only within 24 hours of the start date."
            )
        if hours_difference < 2:
            raise HTTPException(
                status_code=400,
                detail="Sick leave cannot be applied within 2 hours of the start date."
            )
    else:
        # Other leaves require 24 hours advance notice
        if hours_difference < 24:
            raise HTTPException(
                status_code=400,
                detail="Leave requests (except sick leave) must be submitted at least 24 hours in advance."
            )

    # Validation 3: Prevent overlapping leave requests (pending or approved)
    overlapping_leaves = db.query(Leave).filter(
        Leave.user_id == user.user_id,
        Leave.status.in_(["Pending", "Approved"]),
        # (new_start <= old_end) and (new_end >= old_start)
        Leave.start_date <= end_dt,
        Leave.end_date >= start_dt
    ).first()
    if overlapping_leaves:
        raise HTTPException(
            status_code=400,
            detail="You have already applied for leave for some/all of these dates (overlapping leave request detected)."
        )

    # Validation 4: Check remaining leave balance for this leave type
    # Only applies if this leave type is in balance policy
    balances = get_leave_balance(db, user.user_id)
    leave_type = leave.leave_type.lower()
    eligible_types = {b['leave_type'] for b in balances}
    if leave_type in eligible_types:
        # Find matching balance entry
        balance_entry = next((b for b in balances if b['leave_type'] == leave_type), None)
        if balance_entry:
            remaining = balance_entry.get('remaining', 0)
            if leave_days > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough remaining {leave_type} leave. Remaining: {remaining}. Requested: {leave_days}."
                )

    new_leave = apply_leave(
        db,
        user.user_id,
        start_dt,
        end_dt,
        leave.reason,
        leave.leave_type.lower(),
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
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.HR, RoleEnum.ADMIN))
):
    # Load the leave and requester
    leave = db.query(Leave).filter(Leave.leave_id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    if leave.status != "Pending":
        raise HTTPException(status_code=400, detail="Only pending leave requests can be approved/rejected")

    requester = db.query(User).filter(User.user_id == leave.user_id).first()
    if not requester:
        raise HTTPException(status_code=404, detail="Requesting user not found")

    # Prevent self-approval
    if requester.user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="You cannot approve/reject your own leave request")

    requester_role = getattr(requester.role, "value", str(requester.role))

    # Role-based approval rules:
    # - Employee/TeamLead -> Manager or HR (must be same department)
    # - Manager -> Admin or HR
    # - HR -> Admin only
    if requester_role in (RoleEnum.EMPLOYEE.value, RoleEnum.TEAM_LEAD.value):
        if current_user.role not in (RoleEnum.MANAGER, RoleEnum.HR):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Manager or HR can approve/reject this request")
        # Manager/HR may only act on requests from their department
        req_dept = (requester.department or "").strip().lower()
        approver_dept = (current_user.department or "").strip().lower()
        if not req_dept or approver_dept != req_dept:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only approve/reject requests from your department")
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
        updated = approve_leave_db(db, leave_id)
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
    user=Depends(get_current_user)
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
        return list_leave_by_period(db, user.user_id, period, custom_start_date=custom_start, custom_end_date=custom_end)
    else:
        # Default (all) when period omitted, blank, or invalid
        return list_leave_by_period(db, user.user_id, "all")


@router.get("/balance", response_model=LeaveBalanceResponse)
def leave_balance(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    balances = get_leave_balance(db, user.user_id)
    return {"balances": balances}


@router.put("/{leave_id}", response_model=LeaveOut)
def update_leave_request(
    leave_id: int,
    leave_update: LeaveUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # Get the existing leave to check its type
    existing_leave = db.query(Leave).filter(Leave.leave_id == leave_id, Leave.user_id == user.user_id).first()
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
    
    # Use existing values if not provided in update
    final_start_date = start_date or existing_leave.start_date
    final_end_date = end_date or existing_leave.end_date
    final_leave_type = leave_type or existing_leave.leave_type.lower()
    
    # Calculate leave duration for validation
    leave_days = (final_end_date - final_start_date).days + 1

    # Validation 1: Sick leave minimum duration (1 day)
    if final_leave_type == 'sick' and leave_days < 1:
        raise HTTPException(
            status_code=400,
            detail="Sick leave must be for at least 1 day."
        )

    # Validation 2: Advance notice requirements
    now = now_ist()
    time_difference = final_start_date - now
    hours_difference = time_difference.total_seconds() / 3600

    if final_leave_type == 'sick':
        # Sick leave: cannot be for past dates; cannot be for future dates beyond 24 hrs; reject if within 2 hrs of start
        if hours_difference < 0:
            raise HTTPException(
                status_code=400,
                detail="Sick leave cannot be applied for past dates."
            )
        if hours_difference > 24:
            raise HTTPException(
                status_code=400,
                detail="Sick leave cannot be applied for future dates. It must be applied only within 24 hours of the start date."
            )
        if hours_difference < 2:
            raise HTTPException(
                status_code=400,
                detail="Sick leave cannot be applied within 2 hours of the start date."
            )
    else:
        # Other leaves require 24 hours advance notice
        if hours_difference < 24:
            raise HTTPException(
                status_code=400,
                detail="Leave requests (except sick leave) must be submitted at least 24 hours in advance."
            )

    # Validation 3: Prevent overlapping leave requests (pending or approved, excluding the current leave)
    overlapping_leaves = db.query(Leave).filter(
        Leave.user_id == user.user_id,
        Leave.status.in_(["Pending", "Approved"]),
        Leave.leave_id != leave_id,  # Exclude the current leave
        Leave.start_date <= final_end_date,
        Leave.end_date >= final_start_date
    ).first()
    if overlapping_leaves:
        raise HTTPException(
            status_code=400,
            detail="You have already applied for leave for some/all of these dates (overlapping leave request detected)."
        )

    # Validation 4: Check remaining leave balance for this leave type
    # Only applies if this leave type is in balance policy
    balances = get_leave_balance(db, user.user_id)
    eligible_types = {b['leave_type'] for b in balances}
    if final_leave_type in eligible_types:
        # Find matching balance entry
        balance_entry = next((b for b in balances if b['leave_type'] == final_leave_type), None)
        if balance_entry:
            remaining = balance_entry.get('remaining', 0)
            if leave_days > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough remaining {final_leave_type} leave. Remaining: {remaining}. Requested: {leave_days}."
                )

    updated_leave = update_leave_db(
        db,
        leave_id,
        user.user_id,
        start_date=start_date,
        end_date=end_date,
        reason=leave_update.reason,
        leave_type=leave_type,
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
    user=Depends(get_current_user)
):
    result = delete_leave_db(db, leave_id, user.user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Leave not found")
    if result == "not_pending":
        raise HTTPException(status_code=400, detail="Only pending leave requests can be deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Approvals inbox for approvers based on hierarchy
@router.get("/approvals", response_model=list[LeaveHistoryOut])
def approvals_inbox(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # Admin sees only HR/Manager requests
    role_value = getattr(user.role, "value", str(user.role))
    if role_value == RoleEnum.ADMIN.value:
        pending = list_pending_by_requester_roles(db, [RoleEnum.HR.value, RoleEnum.MANAGER.value])
    elif role_value in (RoleEnum.HR.value, RoleEnum.MANAGER.value):
        if not user.department:
            return []
        # HR/Manager see only Employee/TeamLead requests from their department
        pending = list_pending_by_department_and_roles(db, user.department, [RoleEnum.EMPLOYEE.value, RoleEnum.TEAM_LEAD.value])
    else:
        return []

    # enrich with user details
    results = []
    for leave in pending:
        u: User = leave.user
        results.append({
            "leave_id": leave.leave_id,
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
    user=Depends(get_current_user)
):
    """
    Return decided (non-pending) leave decisions visible to the current user:
    - ADMIN: all users except Admins and self.
    - HR: all users except Admins, HRs, and self.
    - MANAGER: users in their department(s), excluding Admins, HRs, other Managers, and self.
    - EMPLOYEE/TEAM_LEAD: their own decided leaves.
    
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
    base_query = db.query(Leave).options(joinedload(Leave.user)).filter(Leave.status != "Pending")

    if role_value == RoleEnum.ADMIN.value:
        # Admin: all users except Admins and self
        decided = (
            base_query.join(User, Leave.user_id == User.user_id)
            .filter(User.role != RoleEnum.ADMIN)
            .filter(User.user_id != user.user_id)
            .order_by(Leave.end_date.desc())
            .all()
        )
    elif role_value == RoleEnum.HR.value:
        # HR: all users except Admins, HRs, and self
        decided = (
            base_query.join(User, Leave.user_id == User.user_id)
            .filter(User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]))
            .filter(User.user_id != user.user_id)
            .order_by(Leave.end_date.desc())
            .all()
        )
    elif role_value == RoleEnum.MANAGER.value:
        # Manager: users in own department(s), excluding Admins, HRs, other Managers, and self.
        if not user.department:
            return []
        manager_dept = user.department
        decided = (
            base_query.join(User, Leave.user_id == User.user_id)
            .filter(User.department == manager_dept)
            .filter(User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]))
            .filter(User.user_id != user.user_id)
            .order_by(Leave.end_date.desc())
            .all()
        )
    elif role_value in (RoleEnum.EMPLOYEE.value, RoleEnum.TEAM_LEAD.value):
        # Employees/TeamLeads see only their own decided leaves
        decided = base_query.filter(Leave.user_id == user.user_id).order_by(Leave.end_date.desc()).all()
    else:
        # Other roles: no access
        return []

    results: list[dict] = []
    for leave in decided:
        u: User = leave.user
        results.append({
            "leave_id": leave.leave_id,
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
    user=Depends(get_current_user)
):
    """Get all leave notifications for the current user."""
    notifications = list_leave_notifications(db, user.user_id)
    return notifications


@router.put("/notifications/{notification_id}/read", response_model=LeaveNotificationOut)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Mark a leave notification as read."""
    notification = mark_leave_notification_as_read(db, notification_id, user.user_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


# ============================================================================
# LEAVE ALLOCATION CONFIGURATION ENDPOINTS (Admin Only)
# ============================================================================

@router.get("/config/allocation", response_model=LeaveAllocationConfigOut)
def get_leave_allocation_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN))
):
    """
    Get the active leave allocation configuration.
    Only accessible by admins.
    """
    config = get_active_leave_config(db)
    
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
    current_user: User = Depends(require_roles(RoleEnum.ADMIN))
):
    """
    Create a new leave allocation configuration.
    This will deactivate all previous configurations and apply the new one globally.
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
        total_annual_leave=total,
        sick_leave_allocation=sick,
        casual_leave_allocation=casual,
        other_leave_allocation=other,
        updated_by=current_user.user_id
    )
    
    return config


@router.put("/config/allocation/{config_id}", response_model=LeaveAllocationConfigOut)
def update_leave_allocation_config_route(
    config_id: int,
    config_data: LeaveAllocationConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN))
):
    """
    Update an existing leave allocation configuration.
    Only accessible by admins.
    """
    config = update_leave_config(
        db=db,
        config_id=config_id,
        sick_leave_allocation=config_data.sick_leave_allocation,
        casual_leave_allocation=config_data.casual_leave_allocation,
        other_leave_allocation=config_data.other_leave_allocation,
        updated_by=current_user.user_id
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
    current_user: User = Depends(get_current_user)
):
    """
    Get the current leave allocation values (for all users).
    Returns default values if no configuration exists.
    Note: annual_leave = sick_leave_allocation + casual_leave_allocation
    """
    config = get_active_leave_config(db)
    
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
