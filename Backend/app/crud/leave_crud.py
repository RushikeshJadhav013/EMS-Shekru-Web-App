from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from typing import List, Optional
from app.db.models.leave import Leave
from app.db.models.notification import LeaveNotification
from app.db.models.user import User
from app.enums import RoleEnum
from app.crud.leave_config_crud import get_leave_config_or_default

DEFAULT_LEAVE_ALLOWANCES = {
    "annual": 15,
    "sick": 10,
    "casual": 5,
}

def apply_leave(
    db: Session,
    user_id: int,
    start_date: datetime,
    end_date: datetime,
    reason: str,
    leave_type: str = "annual",
):
    leave = Leave(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        leave_type=leave_type,
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave

def approve_leave(db: Session, leave_id: int):
    leave = db.query(Leave).filter(Leave.leave_id == leave_id).first()
    if leave:
        leave.status = "Approved"
        db.commit()
        db.refresh(leave)
    return leave

def list_leave(db: Session, user_id: int):
    return db.query(Leave).filter(Leave.user_id == user_id).all()


def update_leave(
    db: Session,
    leave_id: int,
    user_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    reason: Optional[str] = None,
    leave_type: Optional[str] = None,
):
    leave = (
        db.query(Leave)
        .filter(Leave.leave_id == leave_id, Leave.user_id == user_id)
        .first()
    )
    if not leave:
        return None

    if leave.status != "Pending":
        return "not_pending"

    if start_date:
        leave.start_date = start_date
    if end_date:
        leave.end_date = end_date
    if reason is not None:
        leave.reason = reason
    if leave_type:
        leave.leave_type = leave_type

    db.commit()
    db.refresh(leave)
    return leave


def delete_leave(db: Session, leave_id: int, user_id: int):
    leave = (
        db.query(Leave)
        .filter(Leave.leave_id == leave_id, Leave.user_id == user_id)
        .first()
    )
    if not leave:
        return None

    if leave.status != "Pending":
        return "not_pending"

    db.delete(leave)
    db.commit()
    return True


def get_leave_balance(db: Session, user_id: int):
    # Get leave configuration from database or use defaults
    leave_config = get_leave_config_or_default(db)
    
    # Initialize balances with configured values
    balances = {
        "annual": {
            "leave_type": "annual",
            "allocated": leave_config["annual"],
            "used": 0,
            "remaining": leave_config["annual"],
        },
        "sick": {
            "leave_type": "sick",
            "allocated": leave_config["sick"],
            "used": 0,
            "remaining": leave_config["sick"],
        },
        "casual": {
            "leave_type": "casual",
            "allocated": leave_config["casual"],
            "used": 0,
            "remaining": leave_config["casual"],
        },
    }
    
    # Add 'other' leave type if configured
    if leave_config.get("other", 0) > 0:
        balances["other"] = {
            "leave_type": "other",
            "allocated": leave_config["other"],
            "used": 0,
            "remaining": leave_config["other"],
        }

    approved_leaves = (
        db.query(Leave)
        .filter(Leave.user_id == user_id, func.lower(Leave.status) == "approved")
        .all()
    )

    for leave in approved_leaves:
        leave_type = (leave.leave_type or "annual").lower()
        start_date = leave.start_date.date() if isinstance(leave.start_date, datetime) else leave.start_date
        end_date = leave.end_date.date() if isinstance(leave.end_date, datetime) else leave.end_date
        days = (end_date - start_date).days + 1
        if days < 0:
            days = 0

        if leave_type not in balances:
            balances[leave_type] = {
                "leave_type": leave_type,
                "allocated": 0,
                "used": 0,
                "remaining": 0,
            }

        balances[leave_type]["used"] += days

    for leave_type, data in balances.items():
        remaining = data["allocated"] - data["used"]
        data["remaining"] = remaining if remaining >= 0 else 0

    # Return as list sorted by leave type for consistency
    return list(balances.values())


def list_leave_by_period(db: Session, user_id: int, period: str = "current_month") -> List[Leave]:
    """
    Get leave history for a user filtered by time period.
    Shows ALL leaves (pending, approved, rejected) for the user within the specified period.
    period options: "current_month", "last_3_months", "last_6_months", "last_1_year"
    """
    now = datetime.utcnow()
    
    if period == "current_month":
        # Current month only - show leaves that start or end in current month
        month_start = datetime(now.year, now.month, 1)
        if now.month == 12:
            month_end = datetime(now.year + 1, 1, 1)
        else:
            month_end = datetime(now.year, now.month + 1, 1)
        start_date = month_start
        end_date = month_end
    
    elif period == "last_3_months":
        # Last 3 months
        end_date = now
        start_date = now - timedelta(days=90)
    
    elif period == "last_6_months":
        # Last 6 months
        end_date = now
        start_date = now - timedelta(days=180)
    
    elif period == "last_1_year":
        # Last 1 year
        end_date = now
        start_date = now - timedelta(days=365)
    
    else:
        # Default to current month
        month_start = datetime(now.year, now.month, 1)
        if now.month == 12:
            month_end = datetime(now.year + 1, 1, 1)
        else:
            month_end = datetime(now.year, now.month + 1, 1)
        start_date = month_start
        end_date = month_end
    
    # Get ALL leaves for the user where start_date or end_date falls within the period
    # This includes leaves that overlap with the period (pending, approved, rejected)
    # We check both start_date and end_date to catch all relevant leaves
    return (
        db.query(Leave)
        .filter(
            Leave.user_id == user_id,
            # Leave overlaps with the period if:
            # - start_date is within period, OR
            # - end_date is within period, OR
            # - leave spans the entire period
            or_(
                and_(Leave.start_date >= start_date, Leave.start_date < end_date),
                and_(Leave.end_date >= start_date, Leave.end_date < end_date),
                and_(Leave.start_date <= start_date, Leave.end_date >= end_date)
            )
        )
        .order_by(Leave.start_date.desc())
        .all()
    )


def list_pending_all(db: Session):
    return db.query(Leave).filter(Leave.status == "Pending").all()


def list_pending_by_department(db: Session, department: str):
    return (
        db.query(Leave)
        .join(User, User.user_id == Leave.user_id)
        .filter(Leave.status == "Pending", User.department == department)
        .all()
    )


def list_pending_by_requester_roles(db: Session, roles: list[str]):
    return (
        db.query(Leave)
        .join(User, User.user_id == Leave.user_id)
        .filter(Leave.status == "Pending", User.role.in_(roles))
        .all()
    )


def list_pending_by_department_and_roles(db: Session, department: str, roles: list[str]):
    return (
        db.query(Leave)
        .join(User, User.user_id == Leave.user_id)
        .filter(Leave.status == "Pending", User.department == department, User.role.in_(roles))
        .all()
    )


def list_decided_by_approver(db: Session, approver_id: int):
    # Fallback implementation without approver tracking fields.
    # Returns all leaves that have been decided (not Pending).
    return (
        db.query(Leave)
        .filter(Leave.status != "Pending")
        .order_by(Leave.end_date.desc())
        .all()
    )


def _get_leave_notification_recipients(db: Session, requester: User) -> List[User]:
    """
    Get notification recipients based on requester's role and department:
    - Employee/TeamLead → notify Manager & HR from same department ONLY
    - Manager/HR → notify Admin only
    """
    role_value = getattr(requester.role, "value", str(requester.role))
    requester_role = role_value
    requester_department = requester.department
    
    # Employee or TeamLead: notify Manager & HR from same department ONLY
    if role_value in (RoleEnum.EMPLOYEE.value, RoleEnum.TEAM_LEAD.value):
        if not requester.department:
            return []

        
        # Normalize department for comparison (trim whitespace)
        requester_dept = requester.department.strip() if requester.department else None
        if not requester_dept:
            return []
        
        # Get Manager and HR from the EXACT same department only
        # Use case-insensitive comparison to handle "Sales" vs "sales" vs "SALES"
        # First get all potential recipients, then filter in Python for exact match (more reliable)
        all_managers_hr = (
            db.query(User)
            .filter(
                User.department.isnot(None),
                User.role.in_([RoleEnum.MANAGER, RoleEnum.HR]),
                User.is_active == True
            )
            .all()
        )
        
        # Filter by exact department match (case-insensitive, trimmed) and exclude the requester
        recipients = [
            user for user in all_managers_hr
            if user.department 
            and user.department.strip().lower() == requester_dept.lower()
            and user.user_id != requester.user_id  # Exclude the requester themselves
        ]
        return recipients

    # Manager or HR: notify Admin only (exclude the requester)
    elif role_value in (RoleEnum.MANAGER.value, RoleEnum.HR.value):
        recipients = (
            db.query(User)
            .filter(
                User.role == RoleEnum.ADMIN,
                User.is_active == True,  # Only active users
                User.user_id != requester.user_id  # Exclude the requester themselves
            )
            .all()
        )
        return recipients
    
    # Admin or other roles: no notifications
    return []


def create_leave_request_notifications(db: Session, leave: Leave, requester: User) -> List[LeaveNotification]:
    """
    Create notifications for leave request recipients based on department and role hierarchy.
    """
    recipients = _get_leave_notification_recipients(db, requester)
    if not recipients:
        return []

    # Format dates
    start_str = leave.start_date.strftime("%d %b %Y")
    end_str = leave.end_date.strftime("%d %b %Y")
    day_count = (leave.end_date.date() - leave.start_date.date()).days + 1
    day_label = "day" if day_count == 1 else "days"

    title = "Leave Request Submitted"
    message = (
        f"{requester.name} ({requester.employee_id or 'N/A'}) from {requester.department or 'N/A'} department "
        f"has requested leave from {start_str} to {end_str} ({day_count} {day_label})."
    )

    notifications: List[LeaveNotification] = []
    for recipient in recipients:
        notification = LeaveNotification(
            user_id=recipient.user_id,
            leave_id=leave.leave_id,
            notification_type="Leave Request",
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


def create_leave_decision_notification(
    db: Session,
    *,
    leave: Leave,
    approver: User,
    approved: bool,
) -> Optional[LeaveNotification]:
    """Notify the requester when their leave is approved or rejected."""
    requester = db.query(User).filter(User.user_id == leave.user_id).first()
    if not requester:
        return None

    if requester.user_id == approver.user_id:
        return None

    decision = "approved" if approved else "rejected"
    title = f"Leave Request {decision.capitalize()}"

    start_str = leave.start_date.strftime("%d %b %Y") if leave.start_date else ""
    end_str = leave.end_date.strftime("%d %b %Y") if leave.end_date else ""

    message = (
        f"Your leave request from {start_str} to {end_str} "
        f"has been {decision} by {approver.name or 'your approver'}."
    )

    notification = LeaveNotification(
        user_id=requester.user_id,
        leave_id=leave.leave_id,
        notification_type=title,
        title=title,
        message=message,
        is_read=False,
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    return notification


def list_leave_notifications(db: Session, user_id: int) -> List[LeaveNotification]:
    """Get all leave notifications for a user, ordered by most recent first."""
    return (
        db.query(LeaveNotification)
        .filter(LeaveNotification.user_id == user_id)
        .order_by(LeaveNotification.created_at.desc())
        .all()
    )


def mark_leave_notification_as_read(db: Session, notification_id: int, user_id: int) -> Optional[LeaveNotification]:
    """Mark a leave notification as read for a specific user."""
    notification = (
        db.query(LeaveNotification)
        .filter(
            LeaveNotification.notification_id == notification_id,
            LeaveNotification.user_id == user_id,
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
