from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta

from app.db.database import get_db
from app.db.models import User, Attendance, Leave, Task
from app.db.models.office_timing import OfficeTiming
from app.enums import RoleEnum, TaskStatus
from app.dependencies import get_current_user


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _today_bounds():
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    return today_start, today_end


@router.get("/admin")
def admin_dashboard(db: Session = Depends(get_db)):
    today_start, today_end = _today_bounds()

    total_employees = db.query(func.count(User.user_id)).scalar() or 0
    present_today = (
        db.query(func.count(Attendance.attendance_id))
        .filter(Attendance.check_in >= today_start, Attendance.check_in < today_end)
        .scalar()
        or 0
    )
    on_leave_today = (
        db.query(func.count(Leave.leave_id))
        .filter(
            Leave.status == "Approved",
            Leave.start_date <= today_end,
            Leave.end_date >= today_start,
        )
        .scalar()
        or 0
    )
    
    # Calculate late arrivals using office timing configuration
    # First get office timings for proper late calculation
    office_timings_query = db.query(OfficeTiming).filter(OfficeTiming.is_active == True).all()
    office_timings_map = {}
    for timing in office_timings_query:
        key = timing.department if timing.department else "__global__"
        office_timings_map[key] = timing
    
    # Get all attendance records for today with user info for late calculation
    attendance_for_late_calc = (
        db.query(Attendance, User)
        .join(User, User.user_id == Attendance.user_id)
        .filter(Attendance.check_in >= today_start, Attendance.check_in < today_end)
        .all()
    )
    
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
    pending_leaves = (
        db.query(func.count(Leave.leave_id))
        .filter(Leave.status == "Pending")
        .scalar()
        or 0
    )
    active_tasks = (
        db.query(func.count(Task.task_id))
        .filter(Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]))
        .scalar() or 0
    )
    completed_tasks = (
        db.query(func.count(Task.task_id))
        .filter(Task.status == TaskStatus.COMPLETED.value)
        .scalar() or 0
    )
    # Department performance (by presence rate today)
    dept_names = [row[0] for row in db.query(User.department).filter(User.department.isnot(None)).distinct().all()]
    department_performance = []
    for dept in dept_names:
        dept_total = db.query(func.count(User.user_id)).filter(User.department == dept).scalar() or 0
        dept_present = (
            db.query(func.count(Attendance.attendance_id))
            .join(User, User.user_id == Attendance.user_id)
            .filter(User.department == dept, Attendance.check_in >= today_start, Attendance.check_in < today_end)
            .scalar() or 0
        )
        performance = int((dept_present / max(dept_total, 1)) * 100)
        department_performance.append({
            "name": dept,
            "employees": dept_total,
            "performance": performance,
        })

    # Recent activities (today's check-ins)
    attendance_today = (
        db.query(Attendance, User)
        .join(User, User.user_id == Attendance.user_id)
        .filter(Attendance.check_in >= today_start, Attendance.check_in < today_end)
        .order_by(Attendance.check_in.desc())
        .limit(20)
        .all()
    )
    
    # Get office timings for status calculation
    office_timings_map = {}
    office_timings = db.query(OfficeTiming).filter(OfficeTiming.is_active == True).all()
    for timing in office_timings:
        key = timing.department if timing.department else "__global__"
        office_timings_map[key] = timing
    
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
        
        recent_activities.append({
            "id": att.attendance_id,
            "type": "check-in",
            "user": usr.name,
            "time": att.check_in.isoformat(),
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
def hr_dashboard(db: Session = Depends(get_db)):
    today_start, today_end = _today_bounds()

    total_employees = db.query(func.count(User.user_id)).scalar() or 0
    present_today = (
        db.query(func.count(Attendance.attendance_id))
        .filter(Attendance.check_in >= today_start, Attendance.check_in < today_end)
        .scalar()
        or 0
    )
    on_leave_today = (
        db.query(func.count(Leave.leave_id))
        .filter(
            Leave.status == "Approved",
            Leave.start_date <= today_end,
            Leave.end_date >= today_start,
        )
        .scalar()
        or 0
    )
    late_arrivals = (
        db.query(func.count(Attendance.attendance_id))
        .filter(Attendance.check_in >= today_start, Attendance.check_in < today_end)
        .filter(
            func.extract('hour', Attendance.check_in) * 60 + func.extract('minute', Attendance.check_in) > 9 * 60 + 30
        )
        .scalar()
        or 0
    )
    pending_leaves = (
        db.query(func.count(Leave.leave_id)).filter(Leave.status == "Pending").scalar() or 0
    )
    # New joiners and exits this month
    month_start = today_start.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    new_joiners = db.query(func.count(User.user_id)).filter(User.joining_date >= month_start, User.joining_date < next_month).scalar() or 0
    exits = db.query(func.count(User.user_id)).filter(User.resignation_date.isnot(None)).filter(User.resignation_date >= month_start, User.resignation_date < next_month).scalar() or 0
    open_positions = 0  # Not modeled; keep zero or derive from another table if exists

    # Recent HR-related activities
    recent_leave_requests = (
        db.query(Leave, User)
        .join(User, User.user_id == Leave.user_id)
        .order_by(Leave.start_date.desc())
        .limit(12)
        .all()
    )

    attendance_today = (
        db.query(Attendance, User)
        .join(User, User.user_id == Attendance.user_id)
        .filter(Attendance.check_in >= today_start, Attendance.check_in < today_end)
        .order_by(Attendance.check_in.desc())
        .limit(10)
        .all()
    )

    recent_joiners_records = (
        db.query(User)
        .filter(User.joining_date.isnot(None))
        .order_by(User.joining_date.desc())
        .limit(8)
        .all()
    )

    recent_activities = []

    for leave, usr in recent_leave_requests:
        recent_activities.append({
            "id": f"leave-{leave.leave_id}",
            "type": "leave",
            "user": usr.name,
            "time": (leave.start_date or datetime.utcnow()).isoformat(),
            "status": (leave.status or "pending").lower(),
            "description": leave.reason or f"{leave.leave_type or 'Leave'} request",
        })

    # Get office timings for status calculation
    office_timings_map = {}
    office_timings = db.query(OfficeTiming).filter(OfficeTiming.is_active == True).all()
    for timing in office_timings:
        key = timing.department if timing.department else "__global__"
        office_timings_map[key] = timing
    
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
        
        recent_activities.append({
            "id": f"attendance-{att.attendance_id}",
            "type": "attendance",
            "user": usr.name,
            "time": att.check_in.isoformat() if att.check_in else datetime.utcnow().isoformat(),
            "status": status,
            "description": "Checked in",
        })

    for joiner in recent_joiners_records:
        recent_activities.append({
            "id": f"join-{joiner.user_id}",
            "type": "join",
            "user": joiner.name,
            "time": (joiner.joining_date or joiner.created_at or datetime.utcnow()).isoformat(),
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
        "recentActivities": recent_activities,
    }


@router.get("/manager")
def manager_dashboard(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.department:
        raise HTTPException(status_code=400, detail="Manager must have a department assigned")
    dept = current_user.department
    today_start, today_end = _today_bounds()

    team_members = db.query(User).filter(User.department == dept).count()
    present_today = (
        db.query(func.count(Attendance.attendance_id))
        .join(User, User.user_id == Attendance.user_id)
        .filter(User.department == dept, Attendance.check_in >= today_start, Attendance.check_in < today_end)
        .scalar()
        or 0
    )
    on_leave_today = (
        db.query(func.count(Leave.leave_id))
        .join(User, User.user_id == Leave.user_id)
        .filter(User.department == dept, Leave.status == "Approved", Leave.start_date <= today_end, Leave.end_date >= today_start)
        .scalar()
        or 0
    )
    # Task counts by department (based on assigned_to user's department)
    active_tasks = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(User.department == dept, Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]))
        .scalar() or 0
    )
    completed_tasks = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(User.department == dept, Task.status == TaskStatus.COMPLETED.value)
        .scalar() or 0
    )
    pending_approvals = (
        db.query(func.count(Leave.leave_id))
        .join(User, User.user_id == Leave.user_id)
        .filter(
            User.department == dept,
            Leave.status == "Pending",
            User.role.in_([RoleEnum.EMPLOYEE, RoleEnum.TEAM_LEAD]),
            User.is_active.is_(True),
        )
        .scalar()
        or 0
    )
    overdue_items = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(
            User.department == dept,
            Task.status != TaskStatus.COMPLETED.value,
            Task.due_date.isnot(None),
            Task.due_date < datetime.utcnow()
        )
        .scalar() or 0
    )

    total_tasks = active_tasks + completed_tasks
    team_performance_percent = int((completed_tasks / max(total_tasks, 1)) * 100)

    # Recent activities within department (today's check-ins)
    attendance_today = (
        db.query(Attendance, User)
        .join(User, User.user_id == Attendance.user_id)
        .filter(User.department == dept, Attendance.check_in >= today_start, Attendance.check_in < today_end)
        .order_by(Attendance.check_in.desc())
        .limit(20)
        .all()
    )
    # Get office timings for status calculation
    office_timings_map = {}
    office_timings = db.query(OfficeTiming).filter(OfficeTiming.is_active == True).all()
    for timing in office_timings:
        key = timing.department if timing.department else "__global__"
        office_timings_map[key] = timing
    
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
        
        activities.append({
            "id": f"attendance-{att.attendance_id}",
            "type": "attendance",
            "user": usr.name,
            "time": att.check_in.isoformat(),
            "description": "Checked in",
            "status": status,
        })

    pending_leaves = (
        db.query(Leave, User)
        .join(User, User.user_id == Leave.user_id)
        .filter(
            User.department == dept,
            Leave.status == "Pending",
            User.role.in_([RoleEnum.EMPLOYEE, RoleEnum.TEAM_LEAD]),
            User.is_active.is_(True),
        )
        .order_by(Leave.start_date.desc())
        .limit(10)
        .all()
    )
    for leave, usr in pending_leaves:
        activities.append({
            "id": f"leave-{leave.leave_id}",
            "type": "leave",
            "user": usr.name,
            "time": leave.start_date.isoformat(),
            "description": "Leave request pending approval",
            "status": leave.status.lower(),
        })

    recent_tasks = (
        db.query(Task, User)
        .join(User, User.user_id == Task.assigned_to)
        .filter(User.department == dept)
        .order_by(Task.due_date.is_(None), Task.due_date.desc())
        .limit(10)
        .all()
    )
    for task, usr in recent_tasks:
        activities.append({
            "id": f"task-{task.task_id}",
            "type": "task",
            "user": usr.name,
            "time": (task.due_date or datetime.utcnow()).isoformat(),
            "description": task.title,
            "status": task.status.lower(),
        })

    activities.sort(key=lambda item: item["time"], reverse=True)
    team_activities = activities[:15]

    team_leads = db.query(User).filter(User.department == dept, User.role == RoleEnum.TEAM_LEAD).all()
    team_performance = []
    for lead in team_leads:
        lead_tasks = (
            db.query(Task)
            .filter(Task.assigned_by == lead.user_id)
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
        team_performance.append({
            "team": f"{dept} Team",
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
def team_lead_dashboard(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    # Using department as team proxy
    if not current_user.department:
        raise HTTPException(status_code=400, detail="Team Lead must have a department assigned")
    dept = current_user.department
    today_start, today_end = _today_bounds()

    team_size = db.query(User).filter(User.department == dept).count()
    present_today = (
        db.query(func.count(Attendance.attendance_id))
        .join(User, User.user_id == Attendance.user_id)
        .filter(User.department == dept, Attendance.check_in >= today_start, Attendance.check_in < today_end)
        .scalar() or 0
    )
    on_leave_today = (
        db.query(func.count(Leave.leave_id))
        .join(User, User.user_id == Leave.user_id)
        .filter(User.department == dept, Leave.status == "Approved", Leave.start_date <= today_end, Leave.end_date >= today_start)
        .scalar() or 0
    )
    tasks_in_progress = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(User.department == dept, Task.status == TaskStatus.IN_PROGRESS.value)
        .scalar() or 0
    )
    completed_today = (
        db.query(func.count(Task.task_id))
        .join(User, User.user_id == Task.assigned_to)
        .filter(User.department == dept, Task.status == TaskStatus.COMPLETED.value)
        .scalar() or 0
    )
    pending_reviews = 0  # Not modeled
    team_efficiency = 0  # Not modeled

    # Recent activities within team (today's check-ins)
    attendance_today = (
        db.query(Attendance, User)
        .join(User, User.user_id == Attendance.user_id)
        .filter(User.department == dept, Attendance.check_in >= today_start, Attendance.check_in < today_end)
        .order_by(Attendance.check_in.desc())
        .limit(20)
        .all()
    )
    # Get office timings for status calculation
    office_timings_map = {}
    office_timings = db.query(OfficeTiming).filter(OfficeTiming.is_active == True).all()
    for timing in office_timings:
        key = timing.department if timing.department else "__global__"
        office_timings_map[key] = timing
    
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
        
        recent_activities.append({
            "id": att.attendance_id,
            "type": "check-in",
            "user": usr.name,
            "time": att.check_in.isoformat(),
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
def employee_dashboard(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    today_start, today_end = _today_bounds()

    tasks_assigned = db.query(func.count(Task.task_id)).filter(Task.assigned_to == user_id).scalar() or 0
    tasks_completed = db.query(func.count(Task.task_id)).filter(Task.assigned_to == user_id, Task.status == TaskStatus.COMPLETED.value).scalar() or 0
    tasks_pending = db.query(func.count(Task.task_id)).filter(Task.assigned_to == user_id, Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value])).scalar() or 0

    # Leaves available not modeled; return 0 and expose leavesTaken from approved leaves this year
    leaves_taken = db.query(func.count(Leave.leave_id)).filter(Leave.user_id == user_id, Leave.status == "Approved").scalar() or 0

    # Current month hours
    month_start = today_start.replace(day=1)
    total_hours = (
        db.query(func.coalesce(func.sum(Attendance.total_hours), 0.0))
        .filter(Attendance.user_id == user_id, Attendance.check_in >= month_start, Attendance.check_in < today_end)
        .scalar()
        or 0.0
    )
    # Attendance percentage not modeled precisely; compute days present / days elapsed
    days_present = (
        db.query(func.count(Attendance.attendance_id))
        .filter(Attendance.user_id == user_id, Attendance.check_in >= month_start, Attendance.check_in < today_end)
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


