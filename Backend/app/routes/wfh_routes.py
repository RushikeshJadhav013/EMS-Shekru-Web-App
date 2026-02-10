"""
Work From Home (WFH) Request Routes
API endpoints for WFH request management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time
from typing import Optional

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.wfh_request import WFHRequest, WFHStatus
from app.dependencies import get_current_user, require_roles
from app.enums import RoleEnum
from app.utils.timezone import now_ist
from app.utils.department_utils import department_tokens_lower

from app.schemas.wfh_schema import (
    WFHRequestCreate,
    WFHRequestOut,
    WFHRequestWithUserOut,
    WFHRequestApprove,
    WFHRequestUpdate,
    WFHRequestListResponse
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
    get_pending_wfh_count_for_user
)


router = APIRouter(prefix="/wfh", tags=["Work From Home"])

def _can_approver_handle_target(approver: User, target: User) -> bool:
    """
    Determine whether `approver` is allowed to approve/reject `target`'s WFH request
    according to the role-based hierarchy rules:
      - Admins can approve HRs and Managers
      - HRs can approve Managers, TeamLead, and Employees
      - Managers can approve TeamLead and Employees, but only for departments they manage (supports multiple departments)
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

    # Default: no permission
    return False


# ============================================
# Employee Endpoints (All authenticated users)
# ============================================

@router.post("/request", response_model=WFHRequestOut, status_code=status.HTTP_201_CREATED)
def submit_wfh_request(
    payload: WFHRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    
    start_dt = datetime.combine(payload.start_date, time.min)
    # Use 23:59:59 with no microseconds to avoid DB rounding into next day (00:00:00)
    end_dt = datetime.combine(payload.end_date, time(23, 59, 59))
    
    # Validation: 24 hours advance notice for future dates
    now = now_ist()
    if payload.start_date > now.date():
        time_difference = start_dt - now
        hours_difference = time_difference.total_seconds() / 3600
        
        if hours_difference < 24:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WFH requests must be submitted at least 24 hours in advance."
            )
    
    # Check for overlapping requests
    if check_overlapping_wfh(db, current_user.user_id, start_dt, end_dt):
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
        wfh_type=payload.wfh_type
    )
    
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all WFH requests submitted by the current user.
    """
    requests = get_user_wfh_requests(db, current_user.user_id, status_filter)
    
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
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific WFH request submitted by the current user.
    """
    wfh_request = get_wfh_request_by_id(db, wfh_id)
    
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
    current_user: User = Depends(get_current_user)
):
    """
    Update a pending WFH request (only the owner can update).
    """
    wfh_request = get_wfh_request_by_id(db, wfh_id)
    
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
    
    # Check for overlapping requests if dates are being updated
    if start_dt or end_dt:
        check_start = start_dt or wfh_request.start_date
        check_end = end_dt or wfh_request.end_date
        
        if check_overlapping_wfh(db, current_user.user_id, check_start, check_end, exclude_wfh_id=wfh_id):
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
        reason=payload.reason
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update WFH request"
        )
    
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
    current_user: User = Depends(get_current_user)
):
    """
    Delete a pending WFH request (only the owner can delete).
    """
    wfh_request = get_wfh_request_by_id(db, wfh_id)
    
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
    
    deleted = delete_wfh_request(db, wfh_id, current_user.user_id)
    
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.HR, RoleEnum.ADMIN))
):
    """
    Get all WFH requests (for Manager/HR/Admin).
    
    - Manager: Can see requests from their department only
    - HR/Admin: Can see all requests
    
    Supports filtering by status and department.
    """
    requests, pending_count = get_all_wfh_requests(
        db=db,
        status_filter=status_filter,
        department_filter=department,
        requester_user=current_user
    )
    
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
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.HR, RoleEnum.ADMIN))
):
    """
    Get details of a specific WFH request (for Manager/HR/Admin).
    """
    wfh_request = get_wfh_request_by_id(db, wfh_id)
    
    if not wfh_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WFH request not found"
        )
    
    # Get user details
    user = db.query(User).filter(User.user_id == wfh_request.user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Manager can only see requests from their department(s)
    if current_user.role == RoleEnum.MANAGER:
        if not _can_approver_handle_target(current_user, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view requests from your department(s)"
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
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.HR, RoleEnum.ADMIN))
):
    """
    Approve or reject a WFH request (for Manager/HR/Admin).
    
    - Manager: Can approve/reject requests from their department only
    - HR/Admin: Can approve/reject all requests
    """
    wfh_request = get_wfh_request_by_id(db, wfh_id)
    
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
    user = db.query(User).filter(User.user_id == wfh_request.user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request user not found"
        )
    
    # Enforce role-hierarchy approval rules for all approvers (Admin/HR/Manager)
    if not _can_approver_handle_target(current_user, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not permitted to approve/reject this user's WFH request according to role hierarchy"
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
        rejection_reason=payload.rejection_reason
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to process the request"
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
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.HR, RoleEnum.ADMIN))
):
    """
    Get count of pending WFH requests (for Manager/HR/Admin).
    Useful for showing notification badges.
    """
    count = get_pending_wfh_count_for_user(db, current_user)
    return {"pending_count": count}

