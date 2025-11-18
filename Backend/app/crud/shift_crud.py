from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, extract
from datetime import datetime, date, timedelta, time as dt_time
from typing import List, Optional
from app.db.models.shift import Shift, ShiftAssignment, ShiftNotification
from app.db.models.user import User
from app.db.models.leave import Leave
from app.enums import RoleEnum


def create_shift(
    db: Session,
    name: str,
    start_time: str,
    end_time: str,
    department: Optional[str] = None,
    description: Optional[str] = None,
    is_active: bool = True,
):
    """Create a new shift"""
    try:
        start = datetime.strptime(start_time, "%H:%M").time()
        end = datetime.strptime(end_time, "%H:%M").time()
        
        shift = Shift(
            name=name,
            start_time=start,
            end_time=end,
            department=department,
            description=description,
            is_active=is_active,
        )
        db.add(shift)
        db.commit()
        db.refresh(shift)
        return shift
    except Exception as e:
        db.rollback()
        raise ValueError(f"Failed to create shift: {str(e)}")


def get_shift(db: Session, shift_id: int) -> Optional[Shift]:
    """Get a shift by ID"""
    return db.query(Shift).filter(Shift.shift_id == shift_id).first()


def get_shifts_by_department(db: Session, department: Optional[str] = None) -> List[Shift]:
    """Get shifts for a department (or global shifts if department is None)"""
    query = db.query(Shift).filter(Shift.is_active == True)
    
    if department:
        # Get department-specific shifts and global shifts (where department is NULL)
        # Use case-insensitive comparison for department matching
        query = query.filter(
            or_(
                func.lower(Shift.department) == func.lower(department),
                Shift.department.is_(None)
            )
        )
    else:
        # Get only global shifts
        query = query.filter(Shift.department.is_(None))
    
    return query.order_by(Shift.start_time).all()


def update_shift(
    db: Session,
    shift_id: int,
    name: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """Update a shift"""
    shift = db.query(Shift).filter(Shift.shift_id == shift_id).first()
    if not shift:
        return None
    
    if name:
        shift.name = name
    if start_time:
        shift.start_time = datetime.strptime(start_time, "%H:%M").time()
    if end_time:
        shift.end_time = datetime.strptime(end_time, "%H:%M").time()
    if description is not None:
        shift.description = description
    if is_active is not None:
        shift.is_active = is_active
    
    db.commit()
    db.refresh(shift)
    return shift


def delete_shift(db: Session, shift_id: int) -> bool:
    """Permanently delete a shift and cascade related records"""
    shift = db.query(Shift).filter(Shift.shift_id == shift_id).first()
    if not shift:
        return False
    
    try:
        db.delete(shift)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def assign_shift(
    db: Session,
    user_id: int,
    shift_id: int,
    assignment_date: date,
    assigned_by: int,
    notes: Optional[str] = None,
) -> ShiftAssignment:
    """Assign a user to a shift for a specific date"""
    # Check if user already has an assignment for this date
    existing = db.query(ShiftAssignment).filter(
        ShiftAssignment.user_id == user_id,
        ShiftAssignment.assignment_date == assignment_date
    ).first()
    
    is_reassigned = False
    if existing:
        # Update existing assignment (reassignment)
        existing.shift_id = shift_id
        existing.assigned_by = assigned_by
        existing.notes = notes
        existing.is_reassigned = True
        existing.updated_at = datetime.now()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new assignment
        assignment = ShiftAssignment(
            user_id=user_id,
            shift_id=shift_id,
            assignment_date=assignment_date,
            assigned_by=assigned_by,
            notes=notes,
            is_reassigned=False,
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        return assignment


def bulk_assign_shift(
    db: Session,
    user_ids: List[int],
    shift_id: int,
    assignment_date: date,
    assigned_by: int,
    notes: Optional[str] = None,
) -> List[ShiftAssignment]:
    """Bulk assign multiple users to a shift"""
    assignments = []
    for user_id in user_ids:
        assignment = assign_shift(db, user_id, shift_id, assignment_date, assigned_by, notes)
        assignments.append(assignment)
    return assignments


def get_shift_assignment(db: Session, assignment_id: int) -> Optional[ShiftAssignment]:
    """Get a shift assignment by ID"""
    return db.query(ShiftAssignment).filter(ShiftAssignment.assignment_id == assignment_id).first()


def get_user_shift_assignments(
    db: Session,
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[ShiftAssignment]:
    """Get shift assignments for a user within a date range"""
    query = db.query(ShiftAssignment).filter(ShiftAssignment.user_id == user_id)
    
    if start_date:
        query = query.filter(ShiftAssignment.assignment_date >= start_date)
    if end_date:
        query = query.filter(ShiftAssignment.assignment_date <= end_date)
    
    return query.order_by(ShiftAssignment.assignment_date.desc()).all()


def get_department_shift_schedule(
    db: Session,
    department: str,
    schedule_date: date,
) -> dict:
    """Get shift schedule for a department on a specific date"""
    # Get all shifts for the department
    shifts = get_shifts_by_department(db, department)
    
    # Get all assignments for this date
    assignments = db.query(ShiftAssignment).filter(
        ShiftAssignment.assignment_date == schedule_date
    ).all()
    
    # Get users in the department
    department_users = db.query(User).filter(
        User.department == department,
        User.is_active == True,
        User.role.in_([RoleEnum.EMPLOYEE, RoleEnum.TEAM_LEAD])
    ).all()
    
    # Get users on leave for this date
    users_on_leave = db.query(User).join(Leave).filter(
        User.department == department,
        User.is_active == True,
        Leave.start_date <= schedule_date,
        Leave.end_date >= schedule_date,
        Leave.status == "Approved"
    ).all()
    
    # Build shift schedule
    shift_schedule = []
    assigned_user_ids = set()
    
    for shift in shifts:
        shift_assignments = [a for a in assignments if a.shift_id == shift.shift_id]
        assigned_user_ids.update([a.user_id for a in shift_assignments])
        
        shift_schedule.append({
            "shift": shift,
            "assignments": shift_assignments,
            "total_assigned": len(shift_assignments),
        })
    
    # Find unassigned users
    unassigned_users = [u for u in department_users if u.user_id not in assigned_user_ids]
    
    return {
        "department": department,
        "date": schedule_date,
        "shifts": shift_schedule,
        "users_on_leave": users_on_leave,
        "unassigned_users": unassigned_users,
    }


def get_department_shift_schedule_range(
    db: Session,
    department: str,
    start_date: date,
    end_date: date,
) -> dict:
    """Get shift schedules for a department across a date range"""
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    
    days = []
    current_date = start_date
    while current_date <= end_date:
        day_schedule = get_department_shift_schedule(db, department, current_date)
        days.append(day_schedule)
        current_date += timedelta(days=1)
    
    return {
        "department": department,
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
    }


def update_shift_assignment(
    db: Session,
    assignment_id: int,
    shift_id: Optional[int] = None,
    assignment_date: Optional[date] = None,
    notes: Optional[str] = None,
) -> Optional[ShiftAssignment]:
    """Update a shift assignment"""
    assignment = db.query(ShiftAssignment).filter(ShiftAssignment.assignment_id == assignment_id).first()
    if not assignment:
        return None
    
    if shift_id:
        assignment.shift_id = shift_id
        assignment.is_reassigned = True
    if assignment_date:
        assignment.assignment_date = assignment_date
    if notes is not None:
        assignment.notes = notes
    
    assignment.updated_at = datetime.now()
    db.commit()
    db.refresh(assignment)
    return assignment


def delete_shift_assignment(db: Session, assignment_id: int) -> bool:
    """Delete a shift assignment"""
    assignment = db.query(ShiftAssignment).filter(ShiftAssignment.assignment_id == assignment_id).first()
    if not assignment:
        return False
    
    db.delete(assignment)
    db.commit()
    return True


def create_shift_notification(
    db: Session,
    user_id: int,
    shift_assignment_id: int,
    notification_type: str,
    title: str,
    message: str,
) -> ShiftNotification:
    """Create a notification for shift assignment"""
    notification = ShiftNotification(
        user_id=user_id,
        shift_assignment_id=shift_assignment_id,
        notification_type=notification_type,
        title=title,
        message=message,
        is_read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_shift_notifications(db: Session, user_id: int) -> List[ShiftNotification]:
    """Get all shift notifications for a user"""
    return db.query(ShiftNotification).filter(
        ShiftNotification.user_id == user_id
    ).order_by(ShiftNotification.created_at.desc()).all()


def mark_notification_as_read(db: Session, notification_id: int, user_id: int) -> bool:
    """Mark a notification as read"""
    notification = db.query(ShiftNotification).filter(
        ShiftNotification.notification_id == notification_id,
        ShiftNotification.user_id == user_id
    ).first()
    
    if not notification:
        return False
    
    notification.is_read = True
    db.commit()
    return True

