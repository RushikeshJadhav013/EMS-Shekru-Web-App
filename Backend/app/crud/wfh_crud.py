"""
Work From Home (WFH) Request CRUD Operations
Database operations for WFH request management.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, date
from typing import Optional, List, Tuple

from app.db.models.wfh_request import WFHRequest, WFHStatus
from app.db.models.user import User
from app.utils.timezone import now_ist
from app.enums import RoleEnum


def create_wfh_request(
    db: Session,
    user_id: int,
    start_date: datetime,
    end_date: datetime,
    reason: str,
    wfh_type: str = "Full Day"
) -> WFHRequest:
    """
    Create a new WFH request.
    """
    wfh_request = WFHRequest(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        wfh_type=wfh_type,
        reason=reason,
        status=WFHStatus.PENDING.value,
        created_at=now_ist()
    )
    db.add(wfh_request)
    db.commit()
    db.refresh(wfh_request)
    return wfh_request


def get_wfh_request_by_id(db: Session, wfh_id: int) -> Optional[WFHRequest]:
    """
    Get a WFH request by ID.
    """
    return db.query(WFHRequest).filter(WFHRequest.wfh_id == wfh_id).first()


def get_user_wfh_requests(
    db: Session, 
    user_id: int,
    status_filter: Optional[str] = None
) -> List[WFHRequest]:
    """
    Get all WFH requests for a specific user.
    """
    query = db.query(WFHRequest).filter(WFHRequest.user_id == user_id)
    
    if status_filter:
        query = query.filter(WFHRequest.status == status_filter)
    
    return query.order_by(WFHRequest.created_at.desc()).all()


def get_all_wfh_requests(
    db: Session,
    status_filter: Optional[str] = None,
    department_filter: Optional[str] = None,
    requester_user: Optional[User] = None
) -> Tuple[List[dict], int]:
    """
    Get all WFH requests with user details.
    For Manager: show requests from their department
    For HR/Admin: show all requests
    
    Returns: (list of requests with user details, pending count)
    """
    query = (
        db.query(
            WFHRequest,
            User.employee_id,
            User.name,
            User.department,
            User.role
        )
        .join(User, WFHRequest.user_id == User.user_id)
    )
    
    # Role-based filtering
    if requester_user:
        if requester_user.role == RoleEnum.MANAGER:
            # Managers can only see requests from their department
            if requester_user.department:
                query = query.filter(User.department == requester_user.department)
        # HR and Admin can see all requests (no additional filter)
    
    # Status filter
    if status_filter:
        query = query.filter(WFHRequest.status == status_filter)
    
    # Department filter (additional filter for HR/Admin)
    if department_filter:
        query = query.filter(User.department == department_filter)
    
    results = query.order_by(WFHRequest.created_at.desc()).all()
    
    # Count pending requests
    pending_query = db.query(func.count(WFHRequest.wfh_id)).filter(
        WFHRequest.status == WFHStatus.PENDING.value
    )
    if requester_user and requester_user.role == RoleEnum.MANAGER:
        if requester_user.department:
            pending_query = pending_query.join(User).filter(
                User.department == requester_user.department
            )
    pending_count = pending_query.scalar() or 0
    
    # Format results
    formatted_results = []
    for wfh_request, employee_id, name, department, role in results:
        # Get approver name if approved/rejected
        approver_name = None
        if wfh_request.approved_by:
            approver = db.query(User.name).filter(User.user_id == wfh_request.approved_by).scalar()
            approver_name = approver
        
        formatted_results.append({
            "wfh_id": wfh_request.wfh_id,
            "user_id": wfh_request.user_id,
            "employee_id": employee_id,
            "name": name,
            "department": department,
            "role": role.value if role else None,
            "start_date": wfh_request.start_date.date() if wfh_request.start_date else None,
            "end_date": wfh_request.end_date.date() if wfh_request.end_date else None,
            "wfh_type": wfh_request.wfh_type,
            "reason": wfh_request.reason,
            "status": wfh_request.status,
            "approved_by": wfh_request.approved_by,
            "approver_name": approver_name,
            "approved_at": wfh_request.approved_at,
            "rejection_reason": wfh_request.rejection_reason,
            "created_at": wfh_request.created_at,
            "updated_at": wfh_request.updated_at
        })
    
    return formatted_results, pending_count


def approve_wfh_request(
    db: Session,
    wfh_id: int,
    approver_id: int,
    approved: bool,
    rejection_reason: Optional[str] = None
) -> Optional[WFHRequest]:
    """
    Approve or reject a WFH request.
    """
    wfh_request = get_wfh_request_by_id(db, wfh_id)
    if not wfh_request:
        return None
    
    if wfh_request.status != WFHStatus.PENDING.value:
        return None  # Can only approve/reject pending requests
    
    wfh_request.status = WFHStatus.APPROVED.value if approved else WFHStatus.REJECTED.value
    wfh_request.approved_by = approver_id
    wfh_request.approved_at = now_ist()
    wfh_request.updated_at = now_ist()
    
    if not approved and rejection_reason:
        wfh_request.rejection_reason = rejection_reason
    
    db.commit()
    db.refresh(wfh_request)
    return wfh_request


def update_wfh_request(
    db: Session,
    wfh_id: int,
    user_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    wfh_type: Optional[str] = None,
    reason: Optional[str] = None
) -> Optional[WFHRequest]:
    """
    Update a pending WFH request (only the owner can update).
    """
    wfh_request = db.query(WFHRequest).filter(
        WFHRequest.wfh_id == wfh_id,
        WFHRequest.user_id == user_id,
        WFHRequest.status == WFHStatus.PENDING.value
    ).first()
    
    if not wfh_request:
        return None
    
    if start_date:
        wfh_request.start_date = start_date
    if end_date:
        wfh_request.end_date = end_date
    if wfh_type:
        wfh_request.wfh_type = wfh_type
    if reason:
        wfh_request.reason = reason
    
    wfh_request.updated_at = now_ist()
    
    db.commit()
    db.refresh(wfh_request)
    return wfh_request


def delete_wfh_request(db: Session, wfh_id: int, user_id: int) -> bool:
    """
    Delete a pending WFH request (only the owner can delete).
    """
    wfh_request = db.query(WFHRequest).filter(
        WFHRequest.wfh_id == wfh_id,
        WFHRequest.user_id == user_id,
        WFHRequest.status == WFHStatus.PENDING.value
    ).first()
    
    if not wfh_request:
        return False
    
    db.delete(wfh_request)
    db.commit()
    return True


def check_overlapping_wfh(
    db: Session,
    user_id: int,
    start_date: datetime,
    end_date: datetime,
    exclude_wfh_id: Optional[int] = None
) -> bool:
    """
    Check if there's an overlapping approved or pending WFH request.
    Returns True if overlap exists.
    """
    query = db.query(WFHRequest).filter(
        WFHRequest.user_id == user_id,
        WFHRequest.status.in_([WFHStatus.PENDING.value, WFHStatus.APPROVED.value]),
        # Check date overlap: existing.start <= new.end AND existing.end >= new.start
        WFHRequest.start_date <= end_date,
        WFHRequest.end_date >= start_date
    )
    
    if exclude_wfh_id:
        query = query.filter(WFHRequest.wfh_id != exclude_wfh_id)
    
    return query.first() is not None


def get_pending_wfh_count_for_user(db: Session, requester_user: User) -> int:
    """
    Get count of pending WFH requests visible to a user based on their role.
    """
    query = db.query(func.count(WFHRequest.wfh_id)).filter(
        WFHRequest.status == WFHStatus.PENDING.value
    )
    
    if requester_user.role == RoleEnum.MANAGER:
        if requester_user.department:
            query = query.join(User).filter(User.department == requester_user.department)
    
    return query.scalar() or 0

