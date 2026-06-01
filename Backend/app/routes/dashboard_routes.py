from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from typing import Optional

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.attendance import Attendance
from app.db.models.leave import Leave
from app.db.models.task import Task
from app.services.office_timing_service import build_office_timings_map
from app.db.models.department import Department
from app.enums import RoleEnum, TaskStatus
from app.dependencies import get_current_user, require_roles, get_tenant_scope
from app.utils.timezone import now_ist, get_today_bounds_ist
from app.utils.department_utils import department_tokens_lower, department_token_regex_pattern


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


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


def _attendance_scope_filters(scope: dict) -> list:
    return [Attendance.company_id == int(scope["company_id"])]


def _leave_scope_filters(scope: dict) -> list:
    return [Leave.company_id == int(scope["company_id"])]


def _today_bounds():
    """Get today's bounds in IST for database queries"""
    return get_today_bounds_ist()


@router.get("/admin")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    today_start, today_end = _today_bounds()

    # Admin dashboard should not include self or any Admin users.
    base_user_filter = and_(
        User.user_id != current_user.user_id,
        User.role != RoleEnum.ADMIN,
        *_user_scope_filters(scope),
    )

    total_employees = (
        db.query(func.count(User.user_id))
        .filter(base_user_filter)
        .scalar()
        or 0
    )
    present_query = (
        db.query(func.count(Attendance.attendance_id))
        .join(User, User.user_id == Attendance.user_id)
        .filter(
            *_attendance_scope_filters(scope),
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            base_user_filter,
        )
    )
    present_today = present_query.scalar() or 0

    on_leave_query = (
        db.query(func.count(Leave.leave_id))
        .join(User, User.user_id == Leave.user_id)
        .filter(
            *_leave_scope_filters(scope),
            Leave.status == "Approved",
            Leave.start_date <= today_end,
            Leave.end_date >= today_start,
            base_user_filter,
        )
    )
    on_leave_today = on_leave_query.scalar() or 0
    
    # Calculate late arrivals using office timing configuration
    office_timings_map = build_office_timings_map(db, int(scope["company_id"]))
    
    # Get all attendance records for today with user info for late calculation
    attendance_for_late_calc_query = (
        db.query(Attendance, User)
        .join(User, User.user_id == Attendance.user_id)
        .filter(
            *_attendance_scope_filters(scope),
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            base_user_filter,
        )
    )
    attendance_for_late_calc = attendance_for_late_calc_query.all()
    
    late_arrivals = 0
    for att, usr in attendance_for_late_calc:
        # Get applicable office timing (department-specific or global)
        timing = office_timings_map.get(usr.department) or office_timings_map.get("__global__")
        
        if timing:
            # Calculate late threshold (start_time + grace_minutes)
            start_hour = timing.start_time.hour
            start_minute = timing.start_time.minute
            grace_minutes = timing.check_in_grace_minutes or 0
            
            # Convert to total minutes for comparison
            start_total_minutes = start_hour * 60 + start_minute + grace_minutes
            checkin_total_minutes = att.check_in.hour * 60 + att.check_in.minute
            
            if checkin_total_minutes > start_total_minutes:
                late_arrivals += 1
        else:
            # Fallback to default 9:30 AM + 15 min grace = 9:45 AM
            if att.check_in.hour > 9 or (att.check_in.hour == 9 and att.check_in.minute > 45):
                late_arrivals += 1
    # Count pending leaves that admin can actually approve (HR/Manager requests only)
    pending_query = (
        db.query(func.count(Leave.leave_id))
        .join(User, User.user_id == Leave.user_id)
        .filter(
            *_leave_scope_filters(scope),
            Leave.status == "Pending",
            User.role.in_([RoleEnum.HR.value, RoleEnum.MANAGER.value]),
            base_user_filter,
        )
    )
    pending_leaves = pending_query.scalar() or 0

    task_base = (
        db.query(Task)
        .join(User, User.user_id == Task.assigned_to)
        .filter(Task.company_id == int(scope["company_id"]), base_user_filter)
    )

    active_tasks = task_base.filter(Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value])).count() or 0
    completed_tasks = task_base.filter(Task.status == TaskStatus.COMPLETED.value).count() or 0
    department_performance = []

    # Department performance should support users with comma-separated departments by counting
    # users/attendance per department token.
    dept_names = [
        name
        for (name,) in (
            db.query(Department.name)
            .filter(
                Department.status == "active",
                Department.company_id == int(scope["company_id"]),
            )
            .order_by(Department.name.asc())
            .all()
        )
        if name
    ]
    for dept in dept_names:
        dept_pat = department_token_regex_pattern(str(dept).strip().lower())
        dept_token_match = and_(
            User.department.isnot(None),
            func.lower(User.department).op("RLIKE")(dept_pat),
        )
        dept_total = (
            db.query(func.count(User.user_id))
            .filter(base_user_filter, dept_token_match)
            .scalar()
            or 0
        )
        dept_present = (
            db.query(func.count(Attendance.attendance_id))
            .join(User, User.user_id == Attendance.user_id)
            .filter(
                *_attendance_scope_filters(scope),
                Attendance.check_in >= today_start,
                Attendance.check_in < today_end,
                base_user_filter,
                dept_token_match,
            )
            .scalar()
            or 0
        )
        performance = int((dept_present / max(dept_total, 1)) * 100)
        department_performance.append({
            "name": dept,
            "employees": dept_total,
            "performance": performance,
        })

    # Recent activities (today's check-ins)
    attendance_today_query = (
        db.query(Attendance, User)
        .join(User, User.user_id == Attendance.user_id)
        .filter(
            *_attendance_scope_filters(scope),
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            base_user_filter,
        )
    )
    attendance_today = (
        attendance_today_query
        .order_by(Attendance.check_in.desc())
        .limit(20)
        .all()
    )
    
    # Get office timings for status calculation
    from datetime import time as dt_time, timedelta
    
    office_timings_map = build_office_timings_map(db, int(scope["company_id"]))
    
    recent_activities = []
    for att, usr in attendance_today:
        # Get applicable office timing (department-specific or global)
        timing = office_timings_map.get(usr.department) or office_timings_map.get("__global__")
        
        if timing:
            # Calculate late threshold (start_time + grace_minutes)
            start_hour = timing.start_time.hour
            start_minute = timing.start_time.minute
            grace_minutes = timing.check_in_grace_minutes or 0
            
            # Convert to total minutes for comparison
            office_start_minutes = start_hour * 60 + start_minute
            late_threshold_minutes = office_start_minutes + grace_minutes
            checkin_total_minutes = att.check_in.hour * 60 + att.check_in.minute
            
            # Determine status: early, on-time, or late
            if checkin_total_minutes < office_start_minutes:
                status = 'early'
            elif checkin_total_minutes <= late_threshold_minutes:
                status = 'on-time'
            else:
                status = 'late'
        else:
            # Fallback to default 9:30 AM + 15 min grace = 9:45 AM
            office_start_minutes = 9 * 60 + 30  # 9:30 AM = 570 minutes
            late_threshold_minutes = office_start_minutes + 15  # 9:45 AM = 585 minutes
            checkin_total_minutes = att.check_in.hour * 60 + att.check_in.minute
            
            if checkin_total_minutes < office_start_minutes:
                status = 'early'
            elif checkin_total_minutes <= late_threshold_minutes:
                status = 'on-time'
            else:
                status = 'late'
        
        # Check-in time is stored in IST (naive)
        ist_check_in = att.check_in
        recent_activities.append({
            "id": att.attendance_id,
            "type": "check-in",
            "user": usr.name,
            "time": ist_check_in.isoformat(),
            "status": status,
        })

    departments = len(dept_names)

    return {
        "totalEmployees": total_employees,
        "presentToday": present_today,
        "onLeave": on_leave_today,
        "lateArrivals": late_arrivals,
        "pendingLeaves": pending_leaves,
        "activeTasks": active_tasks,
        "completedTasks": completed_tasks,
        "departments": departments,
        "departmentPerformance": department_performance,
        "recentActivities": recent_activities,
    }


@router.get("/hr")
def hr_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    today_start, today_end = _today_bounds()

    # HR dashboard should not include Admins, any HR users, or self.
    hr_base_user_filter = and_(
        User.user_id != current_user.user_id,
        User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]),
        *_user_scope_filters(scope),
    )

    total_employees = (
        db.query(func.count(User.user_id))
        .filter(hr_base_user_filter)
        .scalar()
        or 0
    )
    present_today = (
        db.query(func.count(Attendance.attendance_id))
        .join(User, User.user_id == Attendance.user_id)
        .filter(
            *_attendance_scope_filters(scope),
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            hr_base_user_filter,
        )
        .scalar()
        or 0
    )
    on_leave_today = (
        db.query(func.count(Leave.leave_id))
        .join(User, User.user_id == Leave.user_id)
        .filter(
            *_leave_scope_filters(scope),
            Leave.status == "Approved",
            Leave.start_date <= today_end,
            Leave.end_date >= today_start,
            hr_base_user_filter,
        )
        .scalar()
        or 0
    )
    late_arrivals = (
        db.query(func.count(Attendance.attendance_id))
        .join(User, User.user_id == Attendance.user_id)
        .filter(
            *_attendance_scope_filters(scope),
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            hr_base_user_filter,
            func.extract("hour", Attendance.check_in) * 60
            + func.extract("minute", Attendance.check_in)
            > 9 * 60 + 30,
        )
        .scalar()
        or 0
    )
    # Count pending leaves that HR can actually approve (Employee/TeamLead requests from their department)
    # Note: This is a simplified count - actual HR users should have department filtering
    pending_leaves = (
        db.query(func.count(Leave.leave_id))
        .join(User, User.user_id == Leave.user_id)
        .filter(
            *_leave_scope_filters(scope),
            Leave.status == "Pending",
            User.role.in_([RoleEnum.EMPLOYEE.value, RoleEnum.TEAM_LEAD.value])
            ,
            *_user_scope_filters(scope),
        )
        .scalar()
        or 0
    )
    # New joiners and exits this month
    month_start = today_start.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    new_joiners = db.query(func.count(User.user_id)).filter(User.joining_date >= month_start, User.joining_date < next_month).scalar() or 0
    exits = db.query(func.count(User.user_id)).filter(User.resignation_date.isnot(None)).filter(User.resignation_date >= month_start, User.resignation_date < next_month).scalar() or 0
    open_positions = 0  # Not modeled; keep zero or derive from another table if exists

    # Task statistics for HR
    active_tasks = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(
            hr_base_user_filter,
            Task.status.in_(
                [TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]
            ),
        )
        .scalar()
        or 0
    )
    completed_tasks = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(
            hr_base_user_filter,
            Task.status == TaskStatus.COMPLETED.value,
        )
        .scalar()
        or 0
    )

    # Recent HR-related activities
    recent_leave_requests = (
        db.query(Leave, User)
        .join(User, User.user_id == Leave.user_id)
        .filter(*_leave_scope_filters(scope), hr_base_user_filter)
        .order_by(Leave.start_date.desc())
        .limit(12)
        .all()
    )

    attendance_today = (
        db.query(Attendance, User)
        .join(User, User.user_id == Attendance.user_id)
        .filter(
            *_attendance_scope_filters(scope),
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            hr_base_user_filter,
        )
        .order_by(Attendance.check_in.desc())
        .limit(10)
        .all()
    )

    recent_joiners_records = (
        db.query(User)
        .filter(
            User.joining_date.isnot(None),
            hr_base_user_filter,
        )
        .order_by(User.joining_date.desc())
        .limit(8)
        .all()
    )

    recent_activities = []

    for leave, usr in recent_leave_requests:
        # Convert leave start_date to IST for frontend display
        leave_time = leave.start_date or now_ist()
        if leave_time.tzinfo is None:
            leave_time = leave_time
        recent_activities.append({
            "id": f"leave-{leave.leave_id}",
            "type": "leave",
            "user": usr.name,
            "time": leave_time.isoformat(),
            "status": (leave.status or "pending").lower(),
            "description": leave.reason or f"{leave.leave_type or 'Leave'} request",
        })

    # Get office timings for status calculation
    office_timings_map = build_office_timings_map(db, int(scope["company_id"]))
    
    for att, usr in attendance_today:
        # Get applicable office timing (department-specific or global)
        timing = office_timings_map.get(usr.department) or office_timings_map.get("__global__")
        
        if timing:
            # Calculate late threshold (start_time + grace_minutes)
            start_hour = timing.start_time.hour
            start_minute = timing.start_time.minute
            grace_minutes = timing.check_in_grace_minutes or 0
            
            # Convert to total minutes for comparison
            office_start_minutes = start_hour * 60 + start_minute
            late_threshold_minutes = office_start_minutes + grace_minutes
            checkin_total_minutes = att.check_in.hour * 60 + att.check_in.minute
            
            # Determine status: early, on-time, or late
            if checkin_total_minutes < office_start_minutes:
                status = 'early'
            elif checkin_total_minutes <= late_threshold_minutes:
                status = 'on-time'
            else:
                status = 'late'
        else:
            # Fallback to default 9:30 AM + 15 min grace = 9:45 AM (consistent with admin)
            office_start_minutes = 9 * 60 + 30  # 9:30 AM = 570 minutes
            late_threshold_minutes = office_start_minutes + 15  # 9:45 AM = 585 minutes
            checkin_total_minutes = att.check_in.hour * 60 + att.check_in.minute
            
            if checkin_total_minutes < office_start_minutes:
                status = 'early'
            elif checkin_total_minutes <= late_threshold_minutes:
                status = 'on-time'
            else:
                status = 'late'
        
        # Convert UTC check_in time to IST for frontend display
        check_in_time = att.check_in if att.check_in else now_ist()
        ist_check_in = check_in_time
        recent_activities.append({
            "id": f"attendance-{att.attendance_id}",
            "type": "attendance",
            "user": usr.name,
            "time": ist_check_in.isoformat(),
            "status": status,
            "description": "Checked in",
        })

    for joiner in recent_joiners_records:
        # Convert joining date to IST for frontend display
        join_time = joiner.joining_date or joiner.created_at or now_ist()
        if join_time.tzinfo is None:
            join_time = join_time
        recent_activities.append({
            "id": f"join-{joiner.user_id}",
            "type": "join",
            "user": joiner.name,
            "time": join_time.isoformat(),
            "status": "new-joiner",
            "description": f"Joined {joiner.department or 'company'}",
        })

    recent_activities.sort(key=lambda item: item.get("time") or "", reverse=True)
    recent_activities = recent_activities[:15]

    return {
        "totalEmployees": total_employees,
        "presentToday": present_today,
        "onLeave": on_leave_today,
        "lateArrivals": late_arrivals,
        "pendingLeaves": pending_leaves,
        "newJoinersThisMonth": new_joiners,
        "exitingThisMonth": exits,
        "openPositions": open_positions,
        "activeTasks": active_tasks,
        "completedTasks": completed_tasks,
        "recentActivities": recent_activities,
    }


@router.get("/manager")
def manager_dashboard(
    current_user: User = Depends(require_roles(RoleEnum.MANAGER)),
    db: Session = Depends(get_db),
    scope: dict = Depends(get_tenant_scope),
):
    dept_tokens = department_tokens_lower(getattr(current_user, "department", None))
    if not dept_tokens:
        raise HTTPException(status_code=400, detail="Manager must have a department assigned")

    # Support comma-separated multiple departments for managers, and users who may also have
    # comma-separated multi-department values.
    patterns = [department_token_regex_pattern(tok) for tok in dept_tokens]
    dept_filters = [func.lower(User.department).op("RLIKE")(pat) for pat in patterns]
    dept_match = and_(User.department.isnot(None), or_(*dept_filters))
    # Limit visibility strictly to Team Leads and Employees within these departments
    visible_roles = [RoleEnum.TEAM_LEAD, RoleEnum.EMPLOYEE]
    role_filter = User.role.in_(visible_roles)

    today_start, today_end = _today_bounds()

    team_members = (
        db.query(User)
        .filter(dept_match, role_filter, *_user_scope_filters(scope))
        .count()
    )
    present_today = (
        db.query(func.count(Attendance.attendance_id))
        .join(User, User.user_id == Attendance.user_id)
        .filter(
            *_attendance_scope_filters(scope),
            dept_match,
            role_filter,
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            *_user_scope_filters(scope),
        )
        .scalar()
        or 0
    )
    on_leave_today = (
        db.query(func.count(Leave.leave_id))
        .join(User, User.user_id == Leave.user_id)
        .filter(
            *_leave_scope_filters(scope),
            dept_match,
            role_filter,
            Leave.status == "Approved",
            Leave.start_date <= today_end,
            Leave.end_date >= today_start,
            *_user_scope_filters(scope),
        )
        .scalar()
        or 0
    )
    # Task counts by department (based on assigned_to user's department)
    active_tasks = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(
            dept_match,
            role_filter,
            Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]),
            *_user_scope_filters(scope),
        )
        .scalar() or 0
    )
    completed_tasks = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(
            dept_match,
            role_filter,
            Task.status == TaskStatus.COMPLETED.value,
            *_user_scope_filters(scope),
        )
        .scalar() or 0
    )
    pending_approvals = (
        db.query(func.count(Leave.leave_id))
        .join(User, User.user_id == Leave.user_id)
        .filter(
            *_leave_scope_filters(scope),
            dept_match,
            Leave.status == "Pending",
            User.role.in_([RoleEnum.EMPLOYEE, RoleEnum.TEAM_LEAD]),
            User.is_active.is_(True),
            *_user_scope_filters(scope),
        )
        .scalar()
        or 0
    )
    overdue_items = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(
            dept_match,
            role_filter,
            Task.status != TaskStatus.COMPLETED.value,
            Task.due_date.isnot(None),
            Task.due_date < now_ist()
            ,
            *_user_scope_filters(scope),
        )
        .scalar() or 0
    )

    total_tasks = active_tasks + completed_tasks
    team_performance_percent = int((completed_tasks / max(total_tasks, 1)) * 100)

    # Recent activities within department (today's check-ins)
    attendance_today = (
        db.query(Attendance, User)
        .join(User, User.user_id == Attendance.user_id)
        .filter(
            *_attendance_scope_filters(scope),
            dept_match,
            role_filter,
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            *_user_scope_filters(scope),
        )
        .order_by(Attendance.check_in.desc())
        .limit(20)
        .all()
    )
    # Get office timings for status calculation
    office_timings_map = build_office_timings_map(db, int(scope["company_id"]))
    
    activities = []
    for att, usr in attendance_today:
        # Get applicable office timing (department-specific or global)
        timing = office_timings_map.get(usr.department) or office_timings_map.get("__global__")
        
        if timing:
            # Calculate late threshold (start_time + grace_minutes)
            start_hour = timing.start_time.hour
            start_minute = timing.start_time.minute
            grace_minutes = timing.check_in_grace_minutes or 0
            
            # Convert to total minutes for comparison
            office_start_minutes = start_hour * 60 + start_minute
            late_threshold_minutes = office_start_minutes + grace_minutes
            checkin_total_minutes = att.check_in.hour * 60 + att.check_in.minute
            
            # Determine status: early, on-time, or late
            if checkin_total_minutes < office_start_minutes:
                status = 'early'
            elif checkin_total_minutes <= late_threshold_minutes:
                status = 'on-time'
            else:
                status = 'late'
        else:
            # Fallback to default 9:30 AM + 15 min grace = 9:45 AM (consistent with admin)
            office_start_minutes = 9 * 60 + 30  # 9:30 AM = 570 minutes
            late_threshold_minutes = office_start_minutes + 15  # 9:45 AM = 585 minutes
            checkin_total_minutes = att.check_in.hour * 60 + att.check_in.minute
            
            if checkin_total_minutes < office_start_minutes:
                status = 'early'
            elif checkin_total_minutes <= late_threshold_minutes:
                status = 'on-time'
            else:
                status = 'late'
        
        # Convert UTC check_in time to IST for frontend display
        ist_check_in = att.check_in
        activities.append({
            "id": f"attendance-{att.attendance_id}",
            "type": "attendance",
            "user": usr.name,
            "time": ist_check_in.isoformat(),
            "description": "Checked in",
            "status": status,
        })

    pending_leaves = (
        db.query(Leave, User)
        .join(User, User.user_id == Leave.user_id)
        .filter(
            *_leave_scope_filters(scope),
            dept_match,
            role_filter,
            Leave.status == "Pending",
            User.is_active.is_(True),
            *_user_scope_filters(scope),
        )
        .order_by(Leave.start_date.desc())
        .limit(10)
        .all()
    )
    for leave, usr in pending_leaves:
        # Convert leave start_date to IST for frontend display
        ist_start_date = leave.start_date if leave.start_date else now_ist()
        activities.append({
            "id": f"leave-{leave.leave_id}",
            "type": "leave",
            "user": usr.name,
            "time": ist_start_date.isoformat(),
            "description": "Leave request pending approval",
            "status": leave.status.lower(),
        })

    recent_tasks = (
        db.query(Task, User)
        .join(User, User.user_id == Task.assigned_to)
        .filter(dept_match, role_filter, *_user_scope_filters(scope))
        .order_by(Task.due_date.is_(None), Task.due_date.desc())
        .limit(10)
        .all()
    )
    for task, usr in recent_tasks:
        # Convert task due_date to IST for frontend display
        task_time = task.due_date or now_ist()
        if task_time.tzinfo is None:
            task_time = task_time
        activities.append({
            "id": f"task-{task.task_id}",
            "type": "task",
            "user": usr.name,
            "time": task_time.isoformat(),
            "description": task.title,
            "status": task.status.lower(),
        })

    activities.sort(key=lambda item: item["time"], reverse=True)
    team_activities = activities[:15]

    team_leads = (
        db.query(User)
        .filter(dept_match, User.role == RoleEnum.TEAM_LEAD, *_user_scope_filters(scope))
        .all()
    )
    team_performance = []
    for lead in team_leads:
        lead_tasks = (
            db.query(Task)
            .filter(
                Task.assigned_by == lead.user_id,
                Task.company_id == int(scope["company_id"]),
            )
            .all()
        )
        total_lead_tasks = len(lead_tasks)
        completed_lead_tasks = len([t for t in lead_tasks if t.status == TaskStatus.COMPLETED.value])
        completion_rate = int((completed_lead_tasks / max(total_lead_tasks, 1)) * 100)
        member_ids = {task.assigned_to for task in lead_tasks if task.assigned_to}
        team_performance.append({
            "team": lead.designation or f"{lead.name}'s Team",
            "lead": lead.name,
            "members": len(member_ids),
            "completion": completion_rate,
        })

    if not team_performance:
        team_label = ", ".join(sorted(dept_tokens)) if dept_tokens else "Team"
        team_performance.append({
            "team": f"{team_label} Team",
            "lead": "N/A",
            "members": team_members,
            "completion": team_performance_percent,
        })

    return {
        "teamMembers": team_members,
        "presentToday": present_today,
        "onLeave": on_leave_today,
        "activeTasks": active_tasks,
        "completedTasks": completed_tasks,
        "pendingApprovals": pending_approvals,
        "overdueItems": overdue_items,
        "teamPerformancePercent": team_performance_percent,
        "teamActivities": team_activities,
        "teamPerformance": team_performance,
    }


@router.get("/team-lead")
def team_lead_dashboard(
    current_user: User = Depends(require_roles(RoleEnum.TEAM_LEAD)),
    db: Session = Depends(get_db),
    scope: dict = Depends(get_tenant_scope),
):
    # Using department as team proxy (supports comma-separated multi-departments)
    if not current_user.department:
        raise HTTPException(status_code=400, detail="Team Lead must have a department assigned")

    dept_tokens = department_tokens_lower(getattr(current_user, "department", None))
    if not dept_tokens:
        raise HTTPException(status_code=400, detail="Team Lead must have a valid department configuration")

    patterns = [department_token_regex_pattern(tok) for tok in dept_tokens]
    dept_filters = [func.lower(User.department).op("RLIKE")(pat) for pat in patterns]
    dept_match = and_(User.department.isnot(None), or_(*dept_filters))
    # Limit visibility strictly to Employees within these departments
    role_filter = User.role == RoleEnum.EMPLOYEE
    today_start, today_end = _today_bounds()

    team_size = db.query(User).filter(dept_match, role_filter, *_user_scope_filters(scope)).count()
    present_today = (
        db.query(func.count(Attendance.attendance_id))
        .join(User, User.user_id == Attendance.user_id)
        .filter(
            *_attendance_scope_filters(scope),
            dept_match,
            role_filter,
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            *_user_scope_filters(scope),
        )
        .scalar()
        or 0
    )
    on_leave_today = (
        db.query(func.count(Leave.leave_id))
        .join(User, User.user_id == Leave.user_id)
        .filter(
            *_leave_scope_filters(scope),
            dept_match,
            role_filter,
            Leave.status == "Approved",
            Leave.start_date <= today_end,
            Leave.end_date >= today_start,
            *_user_scope_filters(scope),
        )
        .scalar()
        or 0
    )
    tasks_in_progress = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(
            dept_match,
            role_filter,
            Task.status == TaskStatus.IN_PROGRESS.value,
            *_user_scope_filters(scope),
        )
        .scalar()
        or 0
    )
    completed_today = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(
            dept_match,
            role_filter,
            Task.status == TaskStatus.COMPLETED.value,
            *_user_scope_filters(scope),
        )
        .scalar()
        or 0
    )
    pending_reviews = 0  # Not modeled
    team_efficiency = 0  # Not modeled

    # Recent activities within team (today's check-ins)
    attendance_today = (
        db.query(Attendance, User)
        .join(User, User.user_id == Attendance.user_id)
        .filter(
            *_attendance_scope_filters(scope),
            dept_match,
            role_filter,
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            *_user_scope_filters(scope),
        )
        .order_by(Attendance.check_in.desc())
        .limit(20)
        .all()
    )
    # Get office timings for status calculation
    office_timings_map = build_office_timings_map(db, int(scope["company_id"]))
    
    recent_activities = []
    for att, usr in attendance_today:
        # Get applicable office timing (department-specific or global)
        timing = office_timings_map.get(usr.department) or office_timings_map.get("__global__")
        
        if timing:
            # Calculate late threshold (start_time + grace_minutes)
            start_hour = timing.start_time.hour
            start_minute = timing.start_time.minute
            grace_minutes = timing.check_in_grace_minutes or 0
            
            # Convert to total minutes for comparison
            office_start_minutes = start_hour * 60 + start_minute
            late_threshold_minutes = office_start_minutes + grace_minutes
            checkin_total_minutes = att.check_in.hour * 60 + att.check_in.minute
            
            # Determine status: early, on-time, or late
            if checkin_total_minutes < office_start_minutes:
                status = 'early'
            elif checkin_total_minutes <= late_threshold_minutes:
                status = 'on-time'
            else:
                status = 'late'
        else:
            # Fallback to default 9:30 AM + 15 min grace = 9:45 AM (consistent with admin)
            office_start_minutes = 9 * 60 + 30  # 9:30 AM = 570 minutes
            late_threshold_minutes = office_start_minutes + 15  # 9:45 AM = 585 minutes
            checkin_total_minutes = att.check_in.hour * 60 + att.check_in.minute
            
            if checkin_total_minutes < office_start_minutes:
                status = 'early'
            elif checkin_total_minutes <= late_threshold_minutes:
                status = 'on-time'
            else:
                status = 'late'
        
        # Convert UTC check_in time to IST for frontend display
        ist_check_in = att.check_in
        recent_activities.append({
            "id": att.attendance_id,
            "type": "check-in",
            "user": usr.name,
            "time": ist_check_in.isoformat(),
            "status": status,
        })

    return {
        "teamSize": team_size,
        "presentToday": present_today,
        "onLeave": on_leave_today,
        "tasksInProgress": tasks_in_progress,
        "completedToday": completed_today,
        "pendingReviews": pending_reviews,
        "teamEfficiency": team_efficiency,
        "recentActivities": recent_activities,
    }


@router.get("/employee")
def employee_dashboard(
    current_user: User = Depends(require_roles(RoleEnum.EMPLOYEE)),
    db: Session = Depends(get_db),
    scope: dict = Depends(get_tenant_scope),
):
    user_id = current_user.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    today_start, today_end = _today_bounds()

    tasks_assigned = db.query(func.count(Task.task_id)).filter(Task.assigned_to == user_id).scalar() or 0
    tasks_completed = db.query(func.count(Task.task_id)).filter(Task.assigned_to == user_id, Task.status == TaskStatus.COMPLETED.value).scalar() or 0
    tasks_pending = db.query(func.count(Task.task_id)).filter(Task.assigned_to == user_id, Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value])).scalar() or 0

    # Leaves available not modeled; return 0 and expose leavesTaken from approved leaves this year
    leaves_taken = (
        db.query(func.count(Leave.leave_id))
        .filter(
            Leave.user_id == user_id,
            Leave.company_id == int(scope["company_id"]),
            Leave.status == "Approved",
        )
        .scalar()
        or 0
    )

    # Current month hours
    month_start = today_start.replace(day=1)
    total_hours = (
        db.query(func.coalesce(func.sum(Attendance.total_hours), 0.0))
        .filter(
            Attendance.user_id == user_id,
            Attendance.company_id == int(scope["company_id"]),
            Attendance.check_in >= month_start,
            Attendance.check_in < today_end,
        )
        .scalar()
        or 0.0
    )
    # Attendance percentage not modeled precisely; compute days present / days elapsed
    days_present = (
        db.query(func.count(Attendance.attendance_id))
        .filter(
            Attendance.user_id == user_id,
            Attendance.company_id == int(scope["company_id"]),
            Attendance.check_in >= month_start,
            Attendance.check_in < today_end,
        )
        .scalar() or 0
    )
    days_elapsed = (today_end - month_start).days
    attendance_percentage = int((days_present / max(days_elapsed, 1)) * 100)

    return {
        "tasksAssigned": tasks_assigned,
        "tasksCompleted": tasks_completed,
        "tasksPending": tasks_pending,
        "leavesAvailable": 0,
        "leavesTaken": leaves_taken,
        "attendancePercentage": attendance_percentage,
        "currentMonthHours": float(total_hours),
    }


