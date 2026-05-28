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
from app.db.models.notification import WFHNotification
from app.utils.timezone import now_ist
from app.enums import RoleEnum
from app.utils.department_utils import department_tokens_lower


def _user_scope_filters(*, company_id: int | None, branch_id: int | None, user_alias=User) -> list:
    clauses = []
    if company_id is not None:
        clauses.append(user_alias.company_id == company_id)
    if branch_id is not None:
        clauses.append(user_alias.branch_id == branch_id)
    return clauses


def _user_in_scope(db: Session, *, user_id: int, company_id: int | None, branch_id: int | None) -> bool:
    if company_id is None and branch_id is None:
        return True
    q = db.query(User.user_id).filter(User.user_id == user_id, User.is_active.is_(True))
    for clause in _user_scope_filters(company_id=company_id, branch_id=branch_id):
        q = q.filter(clause)
    return q.first() is not None


def create_wfh_request(
    db: Session,
    user_id: int,
    start_date: datetime,
    end_date: datetime,
    reason: str,
    wfh_type: str = "Full Day",
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> WFHRequest:
    """
    Create a new WFH request.
    """
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        raise ValueError("User not in tenant scope")
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


def get_wfh_request_by_id(
    db: Session,
    wfh_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[WFHRequest]:
    """
    Get a WFH request by ID.
    """
    q = db.query(WFHRequest).filter(WFHRequest.wfh_id == wfh_id)
    if company_id is not None or branch_id is not None:
        q = q.join(User, WFHRequest.user_id == User.user_id).filter(
            User.is_active.is_(True),
            *_user_scope_filters(company_id=company_id, branch_id=branch_id),
        )
    return q.first()


def get_user_wfh_requests(
    db: Session, 
    user_id: int,
    status_filter: Optional[str] = None,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> List[WFHRequest]:
    """
    Get all WFH requests for a specific user.
    """
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return []

    query = db.query(WFHRequest).filter(WFHRequest.user_id == user_id)
    
    if status_filter:
        query = query.filter(WFHRequest.status == status_filter)
    
    return query.order_by(WFHRequest.created_at.desc()).all()


def get_all_wfh_requests(
    db: Session,
    status_filter: Optional[str] = None,
    department_filter: Optional[str] = None,
    requester_user: Optional[User] = None,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Tuple[List[dict], int]:
    """
    Get all WFH requests with user details.
    Role-based hierarchy validation:
    - Admin: Can see all requests except Admins and self
    - HR: Can see all requests except Admins, HRs, and self
    - Manager: Can see requests from their department(s) only, excluding Admins, HRs, Managers, and self
    - TeamLead: Can see requests from their department(s) only, excluding Admins, HRs, Managers, TeamLeads, and self
    
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

    # Tenant scope filter (Option A via users table)
    if company_id is not None or branch_id is not None:
        query = query.filter(
            User.is_active.is_(True),
            *_user_scope_filters(company_id=company_id, branch_id=branch_id),
        )
    
    # Role-based filtering with hierarchy validation
    if requester_user:
        if requester_user.role == RoleEnum.ADMIN:
            # Admin visibility rules:
            # - For HR and Manager users: only Pending requests
            # - For all other users (non-admin): Approved and Rejected requests
            #   (Admins and self are always excluded)
            base = query.filter(User.user_id != requester_user.user_id)

            if status_filter:
                # Normalize status filter
                normalized_status = status_filter.strip().lower()
                # Map to WFHStatus values if possible
                pending_val = WFHStatus.PENDING.value.lower()
                approved_val = WFHStatus.APPROVED.value.lower()
                rejected_val = WFHStatus.REJECTED.value.lower()

                if normalized_status == pending_val:
                    query = base.filter(
                        User.role.in_([RoleEnum.HR, RoleEnum.MANAGER]),
                        WFHRequest.status == WFHStatus.PENDING.value,
                    )
                elif normalized_status in {approved_val, rejected_val}:
                    # Approved/Rejected for all non-admin users
                    allowed_status = (
                        WFHStatus.APPROVED.value if normalized_status == approved_val
                        else WFHStatus.REJECTED.value
                    )
                    query = base.filter(
                        User.role != RoleEnum.ADMIN,
                        WFHRequest.status == allowed_status,
                    )
                else:
                    # Fallback to original behavior for any unexpected status
                    query = base.filter(WFHRequest.status == status_filter)
            else:
                # No explicit status filter: combine the two rules
                query = base.filter(
                    or_(
                        # Pending requests for HR and Manager
                        and_(
                            User.role.in_([RoleEnum.HR, RoleEnum.MANAGER]),
                            WFHRequest.status == WFHStatus.PENDING.value,
                        ),
                        # Approved/Rejected requests for all non-admin users
                        and_(
                            User.role != RoleEnum.ADMIN,
                            WFHRequest.status.in_([WFHStatus.APPROVED.value, WFHStatus.REJECTED.value]),
                        ),
                    )
                )
        elif requester_user.role == RoleEnum.HR:
            # HR can see all requests except Admins, HRs, and self
            query = query.filter(
                User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]),
                User.user_id != requester_user.user_id
            )
        elif requester_user.role == RoleEnum.MANAGER:
            # Manager can see requests from their department(s) only, excluding Admins, HRs, Managers, and self
            if requester_user.department:
                manager_tokens = department_tokens_lower(requester_user.department)
                if manager_tokens:
                    token_filters = [func.lower(User.department).like(f'%{t}%') for t in manager_tokens]
                    query = query.filter(or_(*token_filters))
            query = query.filter(
                User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]),
                User.user_id != requester_user.user_id
            )
        elif requester_user.role == RoleEnum.TEAM_LEAD:
            # TeamLead can see Employee requests from their department(s) only, excluding self
            if requester_user.department:
                lead_tokens = department_tokens_lower(requester_user.department)
                if lead_tokens:
                    token_filters = [func.lower(User.department).like(f'%{t}%') for t in lead_tokens]
                    query = query.filter(or_(*token_filters))
            query = query.filter(
                User.role == RoleEnum.EMPLOYEE,
                User.user_id != requester_user.user_id
            )
    
    # Status filter (for non-Admin callers, or when Admin fallback above used status_filter directly)
    if status_filter and (not requester_user or requester_user.role != RoleEnum.ADMIN):
        query = query.filter(WFHRequest.status == status_filter)
    
    # Department filter (additional filter for HR/Admin)
    if department_filter:
        # department_filter used by HR/Admin - allow matching comma-separated department values
        dept_tokens = department_tokens_lower(department_filter)
        if dept_tokens:
            token_filters = [func.lower(User.department).like(f'%{t}%') for t in dept_tokens]
            query = query.filter(or_(*token_filters))
    
    results = query.order_by(WFHRequest.created_at.desc()).all()
    
    # Count pending requests
    pending_query = db.query(func.count(WFHRequest.wfh_id)).filter(
        WFHRequest.status == WFHStatus.PENDING.value
    )

    # We'll join `users` at most once for the pending query to avoid duplicate table aliases.
    pending_joined = False

    # Apply role-based hierarchy restrictions for pending count
    if requester_user:
        if not pending_joined:
            pending_query = pending_query.join(User, WFHRequest.user_id == User.user_id)
            pending_joined = True

        if company_id is not None or branch_id is not None:
            pending_query = pending_query.filter(
                User.is_active.is_(True),
                *_user_scope_filters(company_id=company_id, branch_id=branch_id),
            )
        
        if requester_user.role == RoleEnum.ADMIN:
            # Admin can see all pending requests except Admins and self
            pending_query = pending_query.filter(
                User.role != RoleEnum.ADMIN,
                User.user_id != requester_user.user_id
            )
        elif requester_user.role == RoleEnum.HR:
            # HR can see all pending requests except Admins, HRs, and self
            pending_query = pending_query.filter(
                User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]),
                User.user_id != requester_user.user_id
            )
        elif requester_user.role == RoleEnum.MANAGER:
            # Manager can see pending requests from their department(s) only, excluding Admins, HRs, Managers, and self
            if requester_user.department:
                manager_tokens = department_tokens_lower(requester_user.department)
                if manager_tokens:
                    token_filters = [func.lower(User.department).like(f'%{t}%') for t in manager_tokens]
                    pending_query = pending_query.filter(or_(*token_filters))
            pending_query = pending_query.filter(
                User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]),
                User.user_id != requester_user.user_id
            )
        elif requester_user.role == RoleEnum.TEAM_LEAD:
            # TeamLead can see pending Employee requests from their department(s) only, excluding self
            if requester_user.department:
                lead_tokens = department_tokens_lower(requester_user.department)
                if lead_tokens:
                    token_filters = [func.lower(User.department).like(f'%{t}%') for t in lead_tokens]
                    pending_query = pending_query.filter(or_(*token_filters))
            pending_query = pending_query.filter(
                User.role == RoleEnum.EMPLOYEE,
                User.user_id != requester_user.user_id
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
    rejection_reason: Optional[str] = None,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[WFHRequest]:
    """
    Approve or reject a WFH request.
    """
    wfh_request = get_wfh_request_by_id(db, wfh_id, company_id=company_id, branch_id=branch_id)
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
    reason: Optional[str] = None,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[WFHRequest]:
    """
    Update a pending WFH request (only the owner can update).
    """
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return None

    q = db.query(WFHRequest).filter(
        WFHRequest.wfh_id == wfh_id,
        WFHRequest.user_id == user_id,
        WFHRequest.status == WFHStatus.PENDING.value,
    )
    if company_id is not None or branch_id is not None:
        q = q.join(User, WFHRequest.user_id == User.user_id).filter(
            User.is_active.is_(True),
            *_user_scope_filters(company_id=company_id, branch_id=branch_id),
        )
    wfh_request = q.first()
    
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


def delete_wfh_request(
    db: Session,
    wfh_id: int,
    user_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> bool:
    """
    Delete a pending WFH request (only the owner can delete).
    """
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return False

    q = db.query(WFHRequest).filter(
        WFHRequest.wfh_id == wfh_id,
        WFHRequest.user_id == user_id,
        WFHRequest.status == WFHStatus.PENDING.value,
    )
    if company_id is not None or branch_id is not None:
        q = q.join(User, WFHRequest.user_id == User.user_id).filter(
            User.is_active.is_(True),
            *_user_scope_filters(company_id=company_id, branch_id=branch_id),
        )
    wfh_request = q.first()
    
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
    exclude_wfh_id: Optional[int] = None,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> bool:
    """
    Check if there's an overlapping approved or pending WFH request.
    Returns True if overlap exists.
    """
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return False

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
            manager_tokens = department_tokens_lower(requester_user.department)
            if manager_tokens:
                token_filters = [func.lower(User.department).like(f'%{t}%') for t in manager_tokens]
                query = query.join(
                    User, WFHRequest.user_id == User.user_id
                ).filter(
                    or_(*token_filters)
                )
    elif requester_user.role == RoleEnum.TEAM_LEAD:
        if requester_user.department:
            lead_tokens = department_tokens_lower(requester_user.department)
            if lead_tokens:
                token_filters = [func.lower(User.department).like(f'%{t}%') for t in lead_tokens]
                query = query.join(
                    User, WFHRequest.user_id == User.user_id
                ).filter(
                    or_(*token_filters),
                    User.role == RoleEnum.EMPLOYEE,
                    User.user_id != requester_user.user_id,
                )
    
    return query.scalar() or 0


def _get_wfh_notification_recipients(
    db: Session,
    requester: User,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> List[User]:
    """
    Resolve approver-side recipients for WFH request notifications.

    Rules mirror the WFH approval hierarchy:
    - Employee -> TeamLead/Manager/HR (same department)
    - TeamLead -> Manager/HR (same department)
    - Manager -> HR + Admin
    - HR -> Admin
    - Admin/others -> no recipients
    """
    role_value = getattr(requester.role, "value", str(requester.role))
    requester_tokens = set(department_tokens_lower(requester.department))

    if role_value == RoleEnum.EMPLOYEE.value:
        if not requester_tokens:
            return []
        roles_to_notify = [RoleEnum.TEAM_LEAD, RoleEnum.MANAGER, RoleEnum.HR]
        candidates = (
            db.query(User)
            .filter(
                User.role.in_(roles_to_notify),
                User.department.isnot(None),
                User.is_active == True,  # noqa: E712
                User.user_id != requester.user_id,
                *_user_scope_filters(company_id=company_id, branch_id=branch_id),
            )
            .all()
        )
        return [
            user
            for user in candidates
            if set(department_tokens_lower(user.department)).intersection(requester_tokens)
        ]

    if role_value == RoleEnum.TEAM_LEAD.value:
        if not requester_tokens:
            return []
        roles_to_notify = [RoleEnum.MANAGER, RoleEnum.HR]
        candidates = (
            db.query(User)
            .filter(
                User.role.in_(roles_to_notify),
                User.department.isnot(None),
                User.is_active == True,  # noqa: E712
                User.user_id != requester.user_id,
                *_user_scope_filters(company_id=company_id, branch_id=branch_id),
            )
            .all()
        )
        return [
            user
            for user in candidates
            if set(department_tokens_lower(user.department)).intersection(requester_tokens)
        ]

    if role_value == RoleEnum.MANAGER.value:
        return (
            db.query(User)
            .filter(
                User.role.in_([RoleEnum.HR, RoleEnum.ADMIN]),
                User.is_active == True,  # noqa: E712
                User.user_id != requester.user_id,
                *_user_scope_filters(company_id=company_id, branch_id=branch_id),
            )
            .all()
        )

    if role_value == RoleEnum.HR.value:
        return (
            db.query(User)
            .filter(
                User.role == RoleEnum.ADMIN,
                User.is_active == True,  # noqa: E712
                User.user_id != requester.user_id,
                *_user_scope_filters(company_id=company_id, branch_id=branch_id),
            )
            .all()
        )

    return []


def create_wfh_request_notifications(db: Session, wfh_request: WFHRequest, requester: User) -> List[WFHNotification]:
    """Create approver notifications for a newly submitted WFH request."""
    recipients = _get_wfh_notification_recipients(
        db,
        requester,
        company_id=getattr(requester, "company_id", None),
        branch_id=getattr(requester, "branch_id", None),
    )
    if not recipients:
        return []

    start_str = wfh_request.start_date.strftime("%d %b %Y")
    end_str = wfh_request.end_date.strftime("%d %b %Y")
    day_count = (wfh_request.end_date.date() - wfh_request.start_date.date()).days + 1
    day_label = "day" if day_count == 1 else "days"

    title = "WFH Request Submitted"
    message = (
        f"{requester.name} ({requester.employee_id or 'N/A'}) from {requester.department or 'N/A'} department "
        f"has requested WFH from {start_str} to {end_str} ({day_count} {day_label})."
    )

    notifications: List[WFHNotification] = []
    for recipient in recipients:
        notification = WFHNotification(
            user_id=recipient.user_id,
            wfh_id=wfh_request.wfh_id,
            notification_type="WFH Request",
            title=title,
            message=message,
            is_read=False,
        )
        db.add(notification)
        notifications.append(notification)

    db.commit()
    for notification in notifications:
        db.refresh(notification)

    return notifications


def update_wfh_request_notifications(db: Session, wfh_request: WFHRequest, requester: User) -> int:
    """Refresh existing approver notifications when a pending WFH request is edited."""
    existing = (
        db.query(WFHNotification)
        .filter(
            WFHNotification.wfh_id == wfh_request.wfh_id,
            WFHNotification.notification_type == "WFH Request",
        )
        .all()
    )
    if not existing:
        return 0

    start_str = wfh_request.start_date.strftime("%d %b %Y")
    end_str = wfh_request.end_date.strftime("%d %b %Y")
    day_count = (wfh_request.end_date.date() - wfh_request.start_date.date()).days + 1
    day_label = "day" if day_count == 1 else "days"

    title = "WFH Request Updated"
    message = (
        f"{requester.name} ({requester.employee_id or 'N/A'}) from {requester.department or 'N/A'} department "
        f"has updated their WFH request to {start_str} to {end_str} ({day_count} {day_label}) [{wfh_request.wfh_type}]."
    )

    bumped_at = now_ist()
    for notification in existing:
        notification.title = title
        notification.message = message
        notification.is_read = False
        notification.created_at = bumped_at

    db.commit()
    return len(existing)


def create_wfh_decision_notification(
    db: Session,
    *,
    wfh_request: WFHRequest,
    approver: User,
    approved: bool,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[WFHNotification]:
    """Notify the requester that their WFH request was approved or rejected."""
    rq = db.query(User).filter(User.user_id == wfh_request.user_id)
    if company_id is not None or branch_id is not None:
        rq = rq.filter(User.is_active.is_(True), *_user_scope_filters(company_id=company_id, branch_id=branch_id))
    requester = rq.first()
    if not requester or requester.user_id == approver.user_id:
        return None

    decision = "approved" if approved else "rejected"
    title = f"WFH Request {decision.capitalize()}"
    start_str = wfh_request.start_date.strftime("%d %b %Y") if wfh_request.start_date else ""
    end_str = wfh_request.end_date.strftime("%d %b %Y") if wfh_request.end_date else ""
    message = (
        f"Your WFH request from {start_str} to {end_str} has been {decision} by "
        f"{approver.name or 'your approver'}."
    )

    notification = WFHNotification(
        user_id=requester.user_id,
        wfh_id=wfh_request.wfh_id,
        notification_type=title,
        title=title,
        message=message,
        is_read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def create_wfh_deletion_notification(
    db: Session,
    wfh_request: WFHRequest,
    requester: User,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> List[WFHNotification]:
    """Notify approvers when a pending WFH request is withdrawn/deleted."""
    recipients = _get_wfh_notification_recipients(
        db,
        requester,
        company_id=company_id,
        branch_id=branch_id,
    )
    if not recipients:
        return []

    start_str = wfh_request.start_date.strftime("%d %b %Y")
    end_str = wfh_request.end_date.strftime("%d %b %Y")
    day_count = (wfh_request.end_date.date() - wfh_request.start_date.date()).days + 1
    day_label = "day" if day_count == 1 else "days"

    title = "WFH Request Withdrawn"
    message = (
        f"{requester.name} ({requester.employee_id or 'N/A'}) from {requester.department or 'N/A'} department "
        f"has withdrawn their WFH request for {start_str} to {end_str} ({day_count} {day_label})."
    )

    notifications: List[WFHNotification] = []
    for recipient in recipients:
        notification = WFHNotification(
            user_id=recipient.user_id,
            wfh_id=None,
            notification_type="WFH Withdrawal",
            title=title,
            message=message,
            is_read=False,
        )
        db.add(notification)
        notifications.append(notification)

    db.commit()
    for notification in notifications:
        db.refresh(notification)

    return notifications


def list_wfh_notifications(
    db: Session,
    user_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> List[WFHNotification]:
    """Get all WFH notifications for a user, most recent first."""
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return []
    return (
        db.query(WFHNotification)
        .filter(WFHNotification.user_id == user_id)
        .order_by(WFHNotification.created_at.desc())
        .all()
    )


def mark_wfh_notification_as_read(
    db: Session,
    notification_id: int,
    user_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[WFHNotification]:
    """Mark a WFH notification as read for the owning user."""
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return None
    notification = (
        db.query(WFHNotification)
        .filter(
            WFHNotification.notification_id == notification_id,
            WFHNotification.user_id == user_id,
        )
        .first()
    )
    if not notification:
        return None

    if not notification.is_read:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
    return notification

