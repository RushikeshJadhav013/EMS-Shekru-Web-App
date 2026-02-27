"""
Report Routes - Employee Performance and Department Metrics
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status as http_status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, or_
from datetime import datetime, timedelta
from typing import Optional, List
from app.utils.timezone import now_ist, get_date_bounds_ist
import traceback
import io
import csv
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.attendance import Attendance
from app.db.models.task import Task, TaskHistory
from app.db.models.leave import Leave
from app.dependencies import get_current_user, require_roles
from app.enums import RoleEnum, TaskStatus, TaskAction
from app.config.company_config import (
    COMPANY_NAME, COMPANY_ADDRESS, COMPANY_PHONE, COMPANY_EMAIL, COMPANY_WEBSITE
)
from app.utils.department_utils import department_tokens_lower, department_token_regex_pattern

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/leave")
def export_leave_report(
    format: str = Query(..., description="Export format: csv or pdf"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Filter by department"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export Leave Report in CSV or PDF format.
    """
    try:
        start_dt = None
        end_dt = None
        # Role-based access: only Admin and HR can export leave reports
        if current_user.role not in (RoleEnum.ADMIN, RoleEnum.HR):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Only Admin and HR users can access the leave report.",
            )

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

        # Validate date range when both are provided
        if start_dt and end_dt and end_dt < start_dt:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="end_date cannot be before start_date",
            )

        from app.crud.leave_crud import export_leave_csv, export_leave_pdf

        if format.lower() == 'csv':
            output = export_leave_csv(
                db,
                start_date=start_dt,
                end_date=end_dt,
                department=department,
                requester=current_user,
            )
            filename = "leave_report.csv"
            return StreamingResponse(
                output,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        elif format.lower() == 'pdf':
            buffer = export_leave_pdf(
                db,
                start_date=start_dt,
                end_date=end_dt,
                department=department,
                generated_by=current_user.name,
                requester=current_user,
            )
            filename = f"leave_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            return StreamingResponse(
                buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        else:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="Invalid format. Use 'csv' or 'pdf'")

    except HTTPException:
        # Re-raise HTTPExceptions (400/403, etc.) as-is so the correct status code is returned
        raise
    except Exception as e:
        print(f"Leave export error: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating leave report: {str(e)}",
        )


@router.get("/employee-performance")
def get_employee_performance(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., description="Year"),
    department: Optional[str] = Query(None, description="Filter by department"),
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get employee performance metrics for a specific month/year.
    Calculates attendance score and task completion rate from actual data.
    """
    
    # Role-based access: only Admin and HR can access employee performance report
    if current_user.role not in (RoleEnum.ADMIN, RoleEnum.HR):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only Admin and HR users can access the employee performance report.",
        )

    try:
        # Calculate date range for the month
        # Frontend sends 1-indexed month (1-12)
        start_date = datetime(year, month, 1)
        # Calculate end date (first day of next month)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
    except ValueError as e:
        # Handle invalid date
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date: month={month}, year={year}. Error: {str(e)}"
        )
    except Exception as e:
        # Catch any other errors
        print(f"Error in employee-performance: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating employee performance: {str(e)}"
        )
    
    try:
        # Base query for active employees, filtered by viewer role
        query = db.query(User).filter(User.is_active == True)

        # Employment-window filter:
        # - Exclude users who joined after the selected period ends
        # - Exclude users who resigned before the selected period starts
        query = query.filter(
            or_(User.joining_date.is_(None), User.joining_date < end_date),
            or_(User.resignation_date.is_(None), User.resignation_date >= start_date),
        )

        # Admin viewer: cannot see any Admin users or self
        if current_user.role == RoleEnum.ADMIN:
            query = query.filter(
                User.role != RoleEnum.ADMIN,
                User.user_id != current_user.user_id,
            )

        # HR viewer: cannot see Admin users, any HR users (including self), or self
        elif current_user.role == RoleEnum.HR:
            query = query.filter(
                User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]),
                User.user_id != current_user.user_id,
            )
        
        # Apply filters
        if department and department != 'all':
            query = query.filter(User.department == department)
        
        if employee_id:
            query = query.filter(User.employee_id == employee_id)
        
        employees = query.order_by(User.name).all()

        # If an explicit employee_id was requested but is not accessible / not found, return a clearer response
        if employee_id and not employees:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Employee not found or you do not have access to this employee's performance.",
            )
        
        results = []
        for emp in employees:
            # Calculate attendance score
            # Count working days in the month (excluding weekends)
            total_working_days = 0
            current = start_date
            while current < end_date:
                if current.weekday() < 5:  # Monday = 0, Friday = 4
                    total_working_days += 1
                current += timedelta(days=1)
            
            # Count actual attendance days
            attendance_records = db.query(Attendance).filter(
                Attendance.user_id == emp.user_id,
                Attendance.check_in >= start_date,
                Attendance.check_in < end_date
            ).count()
            
            attendance_score = round((attendance_records / total_working_days) * 100) if total_working_days > 0 else 0
            attendance_score = min(attendance_score, 100)  # Cap at 100%
            
            # Calculate task completion rate
            total_tasks = db.query(Task).filter(
                Task.assigned_to == emp.user_id
            ).count()
            
            completed_tasks = db.query(Task).filter(
                Task.assigned_to == emp.user_id,
                Task.status == str(TaskStatus.COMPLETED)
            ).count()
            
            task_completion_rate = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
            
            # Manual ratings default to 0 (will be set via frontend)
            productivity = 0
            quality_score = 0
            
            # Calculate overall rating (only if manual ratings are provided)
            if productivity > 0 and quality_score > 0:
                overall_rating = round((attendance_score + task_completion_rate + productivity + quality_score) / 4)
            else:
                overall_rating = 0
            
            results.append({
                "id": str(emp.user_id),
                "employeeId": emp.employee_id or str(emp.user_id),
                "name": emp.name,
                "department": emp.department or "N/A",
                "role": emp.role.value if hasattr(emp.role, 'value') else str(emp.role),
                "attendanceScore": attendance_score,
                "taskCompletionRate": task_completion_rate,
                "productivity": productivity,
                "qualityScore": quality_score,
                "overallRating": overall_rating,
                "month": start_date.strftime("%B"),
                "year": year,
                "totalTasks": total_tasks,
                "completedTasks": completed_tasks,
                "attendanceDays": attendance_records,
                "workingDays": total_working_days
            })
        
        return {"employees": results}
    except Exception as e:
        print(f"Error processing employees: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing employee data: {str(e)}"
        )


@router.get("/department-metrics")
def get_department_metrics(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., description="Year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get department-wise performance metrics.
    Aggregates employee data by department.
    """

    # Role-based access: only Admin and HR can access department metrics
    if current_user.role not in (RoleEnum.ADMIN, RoleEnum.HR):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only Admin and HR users can access the department metrics report.",
        )

    try:
        # Calculate date range
        # Frontend sends 1-indexed month (1-12)
        start_date = datetime(year, month, 1)
        # Calculate end date (first day of next month)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date: month={month}, year={year}. Error: {str(e)}"
        )
    except Exception as e:
        print(f"Error in department-metrics date calculation: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating date range: {str(e)}"
        )
    
    # Calculate working days
    total_working_days = 0
    current = start_date
    while current < end_date:
        if current.weekday() < 5:
            total_working_days += 1
        current += timedelta(days=1)
    
    # Build department → employees map for the selected month/year,
    # splitting comma-separated department strings and respecting employment window
    # and viewer role visibility rules.
    dept_to_employees = {}
    all_dept_users_query = db.query(User).filter(
        User.is_active == True,
        User.department.isnot(None),
        User.department != '',
        # Joined before the period ends
        or_(User.joining_date.is_(None), User.joining_date < end_date),
        # Not resigned before the period starts
        or_(User.resignation_date.is_(None), User.resignation_date >= start_date),
    )

    # Admin viewer: cannot see any Admin users or self
    if current_user.role == RoleEnum.ADMIN:
        all_dept_users_query = all_dept_users_query.filter(
            User.role != RoleEnum.ADMIN,
            User.user_id != current_user.user_id,
        )
    # HR viewer: cannot see Admin users, any HR users (including self), or self
    elif current_user.role == RoleEnum.HR:
        all_dept_users_query = all_dept_users_query.filter(
            User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]),
            User.user_id != current_user.user_id,
        )

    all_dept_users = all_dept_users_query.all()

    for user in all_dept_users:
        raw_dept = user.department or ""
        for part in raw_dept.split(","):
            dept_name = part.strip()
            if not dept_name:
                continue
            dept_to_employees.setdefault(dept_name, []).append(user)
    
    results = []
    for dept_name, dept_employees in dept_to_employees.items():
        if not dept_employees:
            continue
        
        total_employees = len(dept_employees)
        
        if total_employees == 0:
            continue
        
        # Calculate average attendance
        total_attendance_score = 0
        for emp in dept_employees:
            attendance_count = db.query(Attendance).filter(
                Attendance.user_id == emp.user_id,
                Attendance.check_in >= start_date,
                Attendance.check_in < end_date
            ).count()
            emp_attendance_score = (attendance_count / total_working_days) * 100 if total_working_days > 0 else 0
            total_attendance_score += min(emp_attendance_score, 100)
        
        avg_attendance = round(total_attendance_score / total_employees) if total_employees > 0 else 0
        
        # Calculate tasks for department
        dept_user_ids = [emp.user_id for emp in dept_employees]
        
        tasks_completed = db.query(Task).filter(
            Task.assigned_to.in_(dept_user_ids),
            Task.status == str(TaskStatus.COMPLETED)
        ).count()
        
        tasks_pending = db.query(Task).filter(
            Task.assigned_to.in_(dept_user_ids),
            Task.status.in_([str(TaskStatus.PENDING), str(TaskStatus.IN_PROGRESS)])
        ).count()
        
        # Calculate task completion rate
        total_tasks = tasks_completed + tasks_pending
        task_completion_rate = round((tasks_completed / total_tasks) * 100) if total_tasks > 0 else 0
        
        # Performance score is average of attendance and task completion
        performance_score = round((avg_attendance + task_completion_rate) / 2)
        
        results.append({
            "department": dept_name,
            "totalEmployees": total_employees,
            "avgProductivity": 0,  # Manual rating, calculated from frontend
            "avgAttendance": avg_attendance,
            "tasksCompleted": tasks_completed,
            "tasksPending": tasks_pending,
            "performanceScore": performance_score
        })
    
    # Sort by performance score descending
    results.sort(key=lambda x: x['performanceScore'], reverse=True)
    
    return {"departments": results}


@router.get("/executive-summary")
def get_executive_summary(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., description="Year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get executive summary with top 5 performers and comprehensive metrics.
    Performance calculation includes:
    - Early check-ins (25% weight) - Higher weight for punctuality
    - Task completion rate (30% weight) - Highest weight for productivity
    - Attendance consistency (20% weight)
    - On-time check-outs (15% weight)
    - Leave patterns (10% weight)
    """

    # Role-based access: only Admin and HR can access executive summary
    if current_user.role not in (RoleEnum.ADMIN, RoleEnum.HR):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only Admin and HR users can access the executive summary report.",
        )
    
    # Calculate date range
    # Frontend sends 1-indexed month (1-12)
    try:
        start_date = datetime(year, month, 1)
        # Calculate end date (first day of next month)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date: month={month}, year={year}. Error: {str(e)}"
        )
    
    # Get all active employees whose employment overlaps the selected period,
    # then filter further based on viewer role.
    base_query = db.query(User).filter(
        User.is_active == True,
        # Joined before the period ends
        or_(User.joining_date.is_(None), User.joining_date < end_date),
        # Not resigned before the period starts
        or_(User.resignation_date.is_(None), User.resignation_date >= start_date),
    )

    # Admin viewer: cannot see any Admin users or self
    if current_user.role == RoleEnum.ADMIN:
        employees = base_query.filter(
            User.role != RoleEnum.ADMIN,
            User.user_id != current_user.user_id,
        ).all()
    # HR viewer: cannot see Admin users, any HR users (including self), or self
    elif current_user.role == RoleEnum.HR:
        employees = base_query.filter(
            User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]),
            User.user_id != current_user.user_id,
        ).all()
    
    # Calculate working days
    total_working_days = 0
    current = start_date
    while current < end_date:
        if current.weekday() < 5:
            total_working_days += 1
        current += timedelta(days=1)
    
    # Calculate comprehensive metrics for each employee
    employee_scores = []
    total_performance = 0
    
    for emp in employees:
        # Get attendance records for the month
        attendance_records = db.query(Attendance).filter(
            Attendance.user_id == emp.user_id,
            Attendance.check_in >= start_date,
            Attendance.check_in < end_date
        ).all()
        
        attendance_count = len(attendance_records)
        
        # 1. Early Check-in Score (25% weight) - Higher weight for punctuality
        # Consider check-ins before 9:00 AM as early
        early_checkins = sum(1 for att in attendance_records if att.check_in.time() < datetime.strptime('09:00', '%H:%M').time())
        early_checkin_score = (early_checkins / attendance_count * 100) if attendance_count > 0 else 0
        
        # 2. Task Completion Rate (30% weight) - Highest weight for productivity
        total_tasks = db.query(Task).filter(
            Task.assigned_to == emp.user_id
        ).count()
        
        completed_tasks = db.query(Task).filter(
            Task.assigned_to == emp.user_id,
            Task.status == str(TaskStatus.COMPLETED)
        ).count()
        
        task_completion_score = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0  # 0 if no tasks assigned
        
        # 3. Attendance Consistency (20% weight)
        attendance_consistency_score = (attendance_count / total_working_days * 100) if total_working_days > 0 else 0
        attendance_consistency_score = min(attendance_consistency_score, 100)
        
        # 4. On-time Check-out Score (15% weight)
        # Consider check-outs after 6:00 PM as on-time
        on_time_checkouts = sum(1 for att in attendance_records if att.check_out and att.check_out.time() >= datetime.strptime('18:00', '%H:%M').time())
        checkout_score = (on_time_checkouts / attendance_count * 100) if attendance_count > 0 else 0
        
        # 5. Leave Pattern Score (10% weight) - Lower leaves = better score
        leaves = db.query(Leave).filter(
            Leave.user_id == emp.user_id,
            Leave.start_date >= start_date,
            Leave.end_date < end_date,
            Leave.status == 'approved'
        ).all()
        
        total_leave_days = sum((l.end_date - l.start_date).days + 1 for l in leaves)
        # Inverse scoring: fewer leaves = higher score
        leave_score = max(0, 100 - (total_leave_days / total_working_days * 100)) if total_working_days > 0 else 100
        
        # Skip employees with absolutely no data (no attendance AND no tasks)
        if attendance_count == 0 and total_tasks == 0:
            continue
        
        # Calculate weighted overall score with updated weights
        overall_score = (
            early_checkin_score * 0.25 +
            task_completion_score * 0.30 +
            attendance_consistency_score * 0.20 +
            checkout_score * 0.15 +
            leave_score * 0.10
        )
        
        # Calculate task efficiency (tasks per day)
        task_efficiency = (completed_tasks / attendance_count) if attendance_count > 0 else 0
        
        employee_scores.append({
            "employeeId": emp.employee_id or str(emp.user_id),
            "name": emp.name,
            "department": emp.department or "N/A",
            "role": emp.role.value if hasattr(emp.role, 'value') else str(emp.role),
            "score": round(overall_score, 2),
            "earlyCheckinScore": round(early_checkin_score, 1),
            "taskCompletionScore": round(task_completion_score, 1),
            "attendanceScore": round(attendance_consistency_score, 1),
            "checkoutScore": round(checkout_score, 1),
            "leaveScore": round(leave_score, 1),
            "totalTasks": total_tasks,
            "completedTasks": completed_tasks,
            "attendanceDays": attendance_count,
            "workingDays": total_working_days,
            "totalLeaveDays": total_leave_days,
            "earlyCheckins": early_checkins,
            "onTimeCheckouts": on_time_checkouts,
            "taskEfficiency": round(task_efficiency, 2)
        })
        
        total_performance += overall_score
    
    # Sort by score and get top 5 performers
    employee_scores.sort(key=lambda x: x['score'], reverse=True)
    top_performers = employee_scores[:5] if len(employee_scores) >= 5 else employee_scores
    
    # Calculate average performance
    avg_performance = round(total_performance / len(employee_scores)) if employee_scores else 0
    
    # Total tasks completed
    total_tasks_completed = db.query(Task).filter(
        Task.status == str(TaskStatus.COMPLETED)
    ).count()
    
    # Find best department
    dept_scores = {}
    for emp_score in employee_scores:
        dept = emp_score['department']
        if dept and dept != 'N/A':
            if dept not in dept_scores:
                dept_scores[dept] = []
            dept_scores[dept].append(emp_score['score'])
    
    best_dept = {"name": "N/A", "score": 0}
    for dept, scores in dept_scores.items():
        avg_score = sum(scores) / len(scores)
        if avg_score > best_dept['score']:
            best_dept = {"name": dept, "score": round(avg_score)}
    
    return {
        "topPerformers": top_performers,
        "avgPerformance": avg_performance,
        "totalTasksCompleted": total_tasks_completed,
        "bestDepartment": best_dept,
        "topPerformer": top_performers[0] if top_performers else None,  # For backward compatibility
        "totalEmployeesAnalyzed": len(employee_scores),
        "keyFindings": [
            f"Average employee performance is {avg_performance}%",
            f"Top performer: {top_performers[0]['name']} with {top_performers[0]['score']}% score" if top_performers else "No performance data available",
            f"Total tasks completed: {total_tasks_completed}",
            f"Best performing department: {best_dept['name']} ({best_dept['score']}%)",
            f"Top 5 performers maintain an average score of {round(sum(p['score'] for p in top_performers) / len(top_performers), 1)}%" if top_performers else "No top performers data"
        ],
        "recommendations": [
            "Recognize top performers to maintain motivation",
            "Provide additional support for underperforming employees",
            "Share best practices from high-performing departments",
            "Review task allocation for better efficiency",
            "Implement peer learning sessions with top performers"
        ],
        "actionItems": [
            "Schedule performance review meetings",
            "Plan recognition program for top performers",
            "Conduct training needs assessment",
            "Implement weekly progress tracking",
            "Create mentorship program pairing top performers with others"
        ]
    }


@router.get("/departments")
def get_departments_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get list of all departments with active employees"""

    # Role-based access: only Admin and HR can access departments list
    if current_user.role not in (RoleEnum.ADMIN, RoleEnum.HR):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only Admin and HR users can access the departments list.",
        )

    # Support multiple departments stored as comma-separated values
    raw_departments = db.query(User.department).filter(
        User.is_active == True,
        User.department.isnot(None),
        User.department != ''
    ).all()

    dept_set = set()
    for (dept_str,) in raw_departments:
        if not dept_str:
            continue
        for part in dept_str.split(","):
            name = part.strip()
            if name:
                dept_set.add(name)

    # Return sorted list for consistent ordering
    return {"departments": sorted(dept_set)}



@router.get("/export")
async def export_performance_report(
    format: str = Query(..., description="Export format: csv or pdf"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    employee_id: Optional[str] = Query(None, description="Specific employee ID (optional)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export comprehensive performance report in CSV or PDF format.
    Includes: performance metrics, attendance, tasks, leaves, and leave type summary.
    """

    # Role-based access: only Admin and HR can export this performance report
    if current_user.role not in (RoleEnum.ADMIN, RoleEnum.HR):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only Admin and HR users can access the performance report export.",
        )

    try:
        # Parse dates
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')

        # Validate date range
        if end < start:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid date range. 'end_date' cannot be before 'start_date'.",
            )
        
        # Get employees (base query)
        # Include only employees whose joining_date falls within the selected period
        query = db.query(User).filter(
            User.is_active == True,
            User.joining_date >= start,
            User.joining_date <= end,
        )
        if employee_id:
            query = query.filter(User.employee_id == employee_id)

        employees_raw = query.all()

        # If there are no matching active employees at all, return 404
        if not employees_raw:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="No employees found"
            )

        # Apply role-based visibility on which employees can be included in the export
        employees = employees_raw

        if current_user.role == RoleEnum.ADMIN:
            # Admin cannot see self or any Admin users in this report
            employees = [
                emp for emp in employees
                if getattr(emp, "user_id", None) != current_user.user_id
                and getattr(emp, "role", None) != RoleEnum.ADMIN
            ]
        elif current_user.role == RoleEnum.HR:
            # HR cannot see Admins, self, or other HRs in this report
            employees = [
                emp for emp in employees
                if getattr(emp, "user_id", None) != current_user.user_id
                and getattr(emp, "role", None) not in (RoleEnum.ADMIN, RoleEnum.HR)
            ]

        # If, after applying visibility rules, no employees remain, treat it as access denied
        if not employees:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to export performance report for the requested employees.",
            )

        # Collect comprehensive data for each employee
        report_data = []
        
        for emp in employees:
            # Calculate working days in range
            total_working_days = 0
            current = start
            while current <= end:
                if current.weekday() < 5:  # Monday-Friday
                    total_working_days += 1
                current += timedelta(days=1)
            
            # Attendance data
            attendance_records = db.query(Attendance).filter(
                Attendance.user_id == emp.user_id,
                Attendance.check_in >= start,
                Attendance.check_in <= end
            ).all()
            
            attendance_days = len(attendance_records)
            attendance_score = round((attendance_days / total_working_days) * 100) if total_working_days > 0 else 0
            
            # Calculate late arrivals
            late_count = sum(1 for att in attendance_records if att.check_in.time() > datetime.strptime('09:30', '%H:%M').time())
            
            # Calculate early departures
            early_departure_count = sum(1 for att in attendance_records if att.check_out and att.check_out.time() < datetime.strptime('18:00', '%H:%M').time())
            
            # Task data
            tasks = db.query(Task).filter(
                Task.assigned_to == emp.user_id
            ).all()
            
            total_tasks = len(tasks)
            completed_tasks = sum(1 for t in tasks if t.status == str(TaskStatus.COMPLETED))
            pending_tasks = sum(1 for t in tasks if t.status == str(TaskStatus.PENDING))
            in_progress_tasks = sum(1 for t in tasks if t.status == str(TaskStatus.IN_PROGRESS))
            
            task_completion_rate = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
            
            # Leave data
            leaves = db.query(Leave).filter(
                Leave.user_id == emp.user_id,
                Leave.start_date >= start,
                Leave.end_date <= end
            ).all()
            
            total_leaves = len(leaves)
            approved_leaves = sum(1 for l in leaves if l.status == 'approved')
            pending_leaves = sum(1 for l in leaves if l.status == 'pending')
            rejected_leaves = sum(1 for l in leaves if l.status == 'rejected')
            
            # Leave type breakdown
            leave_types = {}
            for leave in leaves:
                leave_type = leave.leave_type or 'unspecified'
                leave_types[leave_type] = leave_types.get(leave_type, 0) + 1
            
            # Calculate total leave days
            total_leave_days = sum((l.end_date - l.start_date).days + 1 for l in leaves if l.status == 'approved')
            
            # Performance score (average of attendance and task completion)
            performance_score = round((attendance_score + task_completion_rate) / 2)
            
            report_data.append({
                'employee_id': emp.employee_id or str(emp.user_id),
                'name': emp.name,
                'email': emp.email,
                'department': emp.department or 'N/A',
                'designation': emp.designation or 'N/A',
                'role': emp.role.value if hasattr(emp.role, 'value') else str(emp.role),
                
                # Attendance metrics
                'working_days': total_working_days,
                'attendance_days': attendance_days,
                'attendance_score': attendance_score,
                'late_arrivals': late_count,
                'early_departures': early_departure_count,
                'absent_days': total_working_days - attendance_days,
                
                # Task metrics
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'pending_tasks': pending_tasks,
                'in_progress_tasks': in_progress_tasks,
                'task_completion_rate': task_completion_rate,
                
                # Leave metrics
                'total_leaves': total_leaves,
                'approved_leaves': approved_leaves,
                'pending_leaves': pending_leaves,
                'rejected_leaves': rejected_leaves,
                'total_leave_days': total_leave_days,
                'leave_types': leave_types,
                
                # Overall performance
                'performance_score': performance_score,
            })
        
        # Generate export based on format
        if format.lower() == 'csv':
            return generate_csv_export(report_data, start_date, end_date, employee_id)
        elif format.lower() == 'pdf':
            return generate_pdf_export(report_data, start_date, end_date, employee_id)
        else:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid format. Use 'csv' or 'pdf'"
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Use YYYY-MM-DD. Error: {str(e)}"
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions (e.g., date range, access, not found) without wrapping them as 500
        raise e
    except Exception as e:
        print(f"Export error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating export: {str(e)}"
        )


def generate_csv_export(data: List[dict], start_date: str, end_date: str, employee_id: Optional[str]) -> StreamingResponse:
    """Generate CSV export with comprehensive performance data"""
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Performance Report'])
    writer.writerow([f'Period: {start_date} to {end_date}'])
    writer.writerow([f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
    writer.writerow([])
    
    # Write employee data headers
    writer.writerow([
        'Employee ID', 'Name', 'Email', 'Department', 'Designation', 'Role',
        'Working Days', 'Attendance Days', 'Attendance %', 'Late Arrivals', 'Early Departures', 'Absent Days',
        'Total Tasks', 'Completed Tasks', 'Pending Tasks', 'In Progress Tasks', 'Task Completion %',
        'Total Leaves', 'Approved Leaves', 'Pending Leaves', 'Rejected Leaves', 'Total Leave Days',
        'Performance Score'
    ])
    
    # Write employee data
    for emp in data:
        writer.writerow([
            emp['employee_id'], emp['name'], emp['email'], emp['department'], emp['designation'], emp['role'],
            emp['working_days'], emp['attendance_days'], emp['attendance_score'], 
            emp['late_arrivals'], emp['early_departures'], emp['absent_days'],
            emp['total_tasks'], emp['completed_tasks'], emp['pending_tasks'], emp['in_progress_tasks'], 
            emp['task_completion_rate'],
            emp['total_leaves'], emp['approved_leaves'], emp['pending_leaves'], emp['rejected_leaves'], 
            emp['total_leave_days'],
            emp['performance_score']
        ])
    
    # Add leave type breakdown section
    writer.writerow([])
    writer.writerow(['Leave Type Breakdown'])
    writer.writerow(['Employee ID', 'Name', 'Leave Type', 'Count'])
    
    for emp in data:
        for leave_type, count in emp['leave_types'].items():
            writer.writerow([emp['employee_id'], emp['name'], leave_type, count])
    
    # Prepare response
    output.seek(0)
    filename = f"performance_report_{start_date}_to_{end_date}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def generate_pdf_export(data: List[dict], start_date: str, end_date: str, employee_id: Optional[str]) -> StreamingResponse:
    """Generate PDF export with comprehensive performance data"""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    page_width = A4[0]
    available_width = page_width - doc.leftMargin - doc.rightMargin
    # Consistent table width: 90% of available width (leaves some margin on sides)
    table_width = available_width * 0.90
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Title
    title = Paragraph("Performance Report", title_style)
    elements.append(title)
    
    # Report info
    info_data = [
        ['Report Period:', f'{start_date} to {end_date}'],
        ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        ['Total Employees:', str(len(data))]
    ]
    
    info_table = Table(info_data, colWidths=[table_width * 0.4, table_width * 0.6], hAlign='CENTER')
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#d1d5db')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        # Consistent inner spacing on all sides
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # Employee performance summary
    for emp in data:
        # Employee header aligned with table width
        emp_heading = Table(
            [[Paragraph(f"<b>{emp['name']}</b> ({emp['employee_id']})", heading_style)]],
            colWidths=[table_width],
            hAlign="CENTER",
        )
        emp_heading.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(emp_heading)
        
        # Employee details
        emp_details = [
            ['Department:', emp['department'], 'Designation:', emp['designation']],
            ['Email:', emp['email'], 'Role:', emp['role']],
        ]
        
        details_table = Table(
            emp_details,
            colWidths=[
                table_width * 0.20,
                table_width * 0.30,
                table_width * 0.20,
                table_width * 0.30,
            ],
            hAlign='CENTER',
        )
        details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#d1d5db')),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#d1d5db')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            # Consistent inner padding
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black)
        ]))
        
        elements.append(details_table)
        elements.append(Spacer(1, 10))
        
        # Performance metrics
        metrics_data = [
            ['Metric', 'Value', 'Metric', 'Value'],
            ['Attendance Score', f"{emp['attendance_score']}%", 'Task Completion', f"{emp['task_completion_rate']}%"],
            ['Attendance Days', f"{emp['attendance_days']}/{emp['working_days']}", 'Completed Tasks', f"{emp['completed_tasks']}/{emp['total_tasks']}"],
            ['Late Arrivals', str(emp['late_arrivals']), 'Pending Tasks', str(emp['pending_tasks'])],
            ['Early Departures', str(emp['early_departures']), 'In Progress Tasks', str(emp['in_progress_tasks'])],
            ['Absent Days', str(emp['absent_days']), 'Total Leaves', str(emp['total_leaves'])],
            ['Approved Leaves', str(emp['approved_leaves']), 'Total Leave Days', str(emp['total_leave_days'])],
        ]
        
        metrics_table = Table(metrics_data, colWidths=[table_width / 4] * 4, hAlign='CENTER')
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d1d5db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            # Consistent inner padding
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
        ]))
        
        elements.append(metrics_table)
        
        # Leave type breakdown
        if emp['leave_types']:
            elements.append(Spacer(1, 10))
            leave_heading = Table(
                [[Paragraph("<b>Leave Type Breakdown:</b>", styles['Normal'])]],
                colWidths=[table_width],
                hAlign="CENTER",
            )
            leave_heading.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(leave_heading)
            
            leave_data = [['Leave Type', 'Count']]
            for leave_type, count in emp['leave_types'].items():
                leave_data.append([leave_type.title(), str(count)])
            
            leave_table = Table(
                leave_data,
                colWidths=[table_width * 0.6, table_width * 0.4],
                hAlign='CENTER',
            )
            leave_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d1d5db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                # Consistent inner padding
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
            ]))
            
            elements.append(leave_table)
        
        # Performance score highlight
        elements.append(Spacer(1, 10))
        score_color = colors.green if emp['performance_score'] >= 75 else colors.orange if emp['performance_score'] >= 60 else colors.red
        score_data = [['Overall Performance Score', f"{emp['performance_score']}%"]]
        score_table = Table(
            score_data,
            colWidths=[table_width * 0.6, table_width * 0.4],
            hAlign='CENTER',
        )
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), score_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            # Consistent inner padding
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(score_table)
        elements.append(PageBreak())
    
    # Build PDF
    doc.build(elements)
    
    # Prepare response
    buffer.seek(0)
    filename = f"performance_report_{start_date}_to_{end_date}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/task-management")
async def export_task_management_report(
    department: Optional[str] = Query(None, description="Filter by department"),
    period_type: Optional[str] = Query(None, description="Period type: 'monthly', 'quarterly', or 'custom' (default: custom if start_date/end_date provided)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12) for monthly period"),
    quarter: Optional[int] = Query(None, ge=1, le=4, description="Quarter (1-4) for quarterly period"),
    year: Optional[int] = Query(None, description="Year for monthly or quarterly period"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD) for custom period"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD) for custom period"),
    status: Optional[str] = Query(None, description="Filter by task status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export Task Management Report in PDF format.
    Professional report with company branding, task details, and comprehensive information.
    
    Supports time-based filters:
    - Monthly: Use period_type='monthly' with month (1-12) and year
    - Quarterly: Use period_type='quarterly' with quarter (1-4) and year
    - Custom: Use start_date and end_date (YYYY-MM-DD)
    """
    try:
        # Determine period type and calculate date range
        start = None
        end = None
        period_label = "All Time"
        
        # If period_type is explicitly set, use it; otherwise infer from parameters
        if period_type:
            period_type = period_type.lower()
        elif month is not None or quarter is not None:
            # Infer period type from parameters
            if month is not None:
                period_type = 'monthly'
            elif quarter is not None:
                period_type = 'quarterly'
            else:
                period_type = 'custom'
        elif start_date or end_date:
            period_type = 'custom'
        else:
            period_type = None  # No date filter
        
        # Calculate date range based on period type
        if period_type == 'monthly':
            if month is None or year is None:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="For monthly period, both 'month' (1-12) and 'year' are required"
                )
            # month is now 1-12 directly
            start = datetime(year, month, 1)
            # Calculate end date (first day of next month)
            if month == 12:
                end = datetime(year + 1, 1, 1)
            else:
                end = datetime(year, month + 1, 1)
            # Format period label
            month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']
            period_label = f"{month_names[month - 1]} {year}"
        
        elif period_type == 'quarterly':
            if quarter is None or year is None:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="For quarterly period, both 'quarter' (1-4) and 'year' are required"
                )
            # Calculate quarter date range
            if quarter == 1:
                start = datetime(year, 1, 1)
                end = datetime(year, 4, 1)
                period_label = f"Q1 {year} (Jan - Mar)"
            elif quarter == 2:
                start = datetime(year, 4, 1)
                end = datetime(year, 7, 1)
                period_label = f"Q2 {year} (Apr - Jun)"
            elif quarter == 3:
                start = datetime(year, 7, 1)
                end = datetime(year, 10, 1)
                period_label = f"Q3 {year} (Jul - Sep)"
            elif quarter == 4:
                start = datetime(year, 10, 1)
                end = datetime(year + 1, 1, 1)
                period_label = f"Q4 {year} (Oct - Dec)"
        
        elif period_type == 'custom':
            if start_date:
                start = datetime.strptime(start_date, '%Y-%m-%d')
            if end_date:
                end = datetime.strptime(end_date, '%Y-%m-%d')
            if start and end:
                period_label = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
            elif start:
                period_label = f"From {start.strftime('%Y-%m-%d')}"
            elif end:
                period_label = f"Until {end.strftime('%Y-%m-%d')}"
        
        # Parse dates if provided (for backward compatibility)
        if not start and start_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
        if not end and end_date:
            end = datetime.strptime(end_date, '%Y-%m-%d')

        # -----------------------------
        # Scope to tasks directly related to current user only
        # -----------------------------
        query = (
            db.query(Task)
            .outerjoin(TaskHistory, TaskHistory.task_id == Task.task_id)
            .filter(
                or_(
                    Task.assigned_to == current_user.user_id,
                    Task.assigned_by == current_user.user_id,
                    TaskHistory.user_id == current_user.user_id,
                )
            )
            .distinct()
        )
        
        if start:
            query = query.filter(Task.created_at >= start)
        if end:
            # For monthly/quarterly, use < end (exclusive) to match the pattern
            # For custom dates, use <= end (inclusive)
            if period_type and period_type in ['monthly', 'quarterly']:
                query = query.filter(Task.created_at < end)
            else:
                query = query.filter(Task.created_at <= end)
        if status:
            query = query.filter(Task.status == status)
        
        tasks = query.order_by(Task.created_at.desc()).all()
        
        if not tasks:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="No tasks found matching the criteria"
            )
        
        # Get department name for report (use first task's department or filter)
        report_department = department or "All Departments"
        if not department or department == 'all':
            # Try to get a common department from tasks
            dept_users = db.query(User).filter(
                User.user_id.in_([t.assigned_to for t in tasks[:5] if t.assigned_to])
            ).first()
            if dept_users and dept_users.department:
                report_department = dept_users.department
        
        # Generate PDF
        return generate_task_management_pdf(
            tasks=tasks,
            department=report_department,
            generated_by=current_user.name,
            period_label=period_label,
            db=db
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Use YYYY-MM-DD. Error: {str(e)}"
        )
    except Exception as e:
        print(f"Task management report error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating task management report: {str(e)}"
        )


def generate_task_management_pdf(tasks, department, generated_by, period_label, db):
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors

    buffer = io.BytesIO()
    page_size = landscape(A4)
    left_margin = right_margin = 36
    top_margin = bottom_margin = 36
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin
    )
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.black,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    elements.append(Paragraph("Task Management Report", title_style))
    elements.append(Spacer(1, 12))

    # Info block
    info_data = [
        ['Company Name', COMPANY_NAME or ''],
        ['Department', department or 'Any'],
        ['Period', period_label],
        ['Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        ['Generated By', generated_by],
    ]
    info_table = Table(info_data, colWidths=[1.5*inch, (page_size[0] - left_margin - right_margin) - 1.5*inch])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 14))

    # Table headers and data
    all_headers = [
        'Task ID', 'Task Name', 'Description', 'Status', 'Priority',
        'Assigned By', 'Assigned To', 'Created Date', 'Modified Date',
        'Last Passed To', 'Completed By'
    ]
    all_rows = []
    for task in tasks:
        assigned_by = db.query(User).filter(User.user_id == task.assigned_by).first().name if task.assigned_by else "N/A"
        assigned_to = db.query(User).filter(User.user_id == task.assigned_to).first().name if task.assigned_to else "N/A"
        last_passed_to = db.query(User).filter(User.user_id == task.last_passed_to).first().name if task.last_passed_to else "N/A"
        completed_by = "N/A"
        created_date = task.created_at.strftime('%Y-%m-%d') if task.created_at else ""
        modified_date = task.last_passed_at.strftime('%Y-%m-%d') if task.last_passed_at else created_date
        all_rows.append([
            str(task.task_id),
            task.title or "",
            task.description or "",
            task.status or "",
            task.priority or "",
            assigned_by,
            assigned_to,
            created_date,
            modified_date,
            last_passed_to,
            completed_by,
        ])
    
    # Filter out columns with no data (all values are empty or "N/A")
    headers = []
    col_indices = []
    for col_idx, header in enumerate(all_headers):
        has_data = False
        for row in all_rows:
            cell_value = row[col_idx]
            if cell_value and cell_value.strip() and cell_value != "N/A":
                has_data = True
                break
        if has_data:
            headers.append(header)
            col_indices.append(col_idx)
    
    # Build filtered rows with only populated columns
    rows = []
    for row in all_rows:
        filtered_row = [row[idx] for idx in col_indices]
        rows.append(filtered_row)

    num_cols = len(headers)
    total_width = page_size[0] - (left_margin + right_margin)
    col_widths = [total_width / num_cols] * num_cols

    def truncate(text, max_len=32):
        t = str(text)
        return t if len(t) <= max_len else t[:max_len-3] + "..."

    # Table cell styles for wrap
    body_cell_style = ParagraphStyle(
        'body_cell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.black,
        alignment=TA_LEFT,
        leading=11,
        wordWrap='CJK',  # wrapping for long words and CJK chars
    )
    header_cell_style = ParagraphStyle(
        'header_cell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.black,
        alignment=TA_CENTER,
        leading=13,
    )
    # Data for the table, with text wrapping
    table_rows = [[Paragraph(h, header_cell_style) for h in headers]]
    for r in rows:
        table_rows.append([Paragraph(str(x) if x else '', body_cell_style) for x in r])

    table = Table(table_rows, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        # Table body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        # Thin gray grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e6edf3')),
    ]))
    elements.append(table)

    # --- Footer is identical to your leave report ---
    def draw_footer(canvas, doc_obj):
        canvas.saveState()
        footer_font_size = 8
        horizontal_padding = 30
        footer_line_thickness = 0.5
        line_height = 11
        spacing_between_line_and_text = 8
        footer_bottom_padding = 15
        first_line_parts = []
        if COMPANY_ADDRESS:
            first_line_parts.append(COMPANY_ADDRESS)
        if COMPANY_WEBSITE:
            first_line_parts.append(f"Website: {COMPANY_WEBSITE}")
        if COMPANY_EMAIL:
            first_line_parts.append(f"Email: {COMPANY_EMAIL}")
        if COMPANY_PHONE:
            first_line_parts.append(f"Contact: {COMPANY_PHONE}")
        first_line_text = " | ".join(first_line_parts)
        copyright_text = f"© {datetime.now().year} {COMPANY_NAME}. All rights reserved."
        page_text = f"Page {canvas.getPageNumber()}"
        canvas.setFont("Helvetica", footer_font_size)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.setFont("Helvetica-Bold", footer_font_size)
        page_num_width = canvas.stringWidth(page_text, "Helvetica-Bold", footer_font_size)
        canvas.setFont("Helvetica", footer_font_size)
        available_width_line1 = page_size[0] - (horizontal_padding * 2)
        spacing_between_copyright_and_page = 15
        available_width_line2 = page_size[0] - (horizontal_padding * 2) - page_num_width - spacing_between_copyright_and_page
        first_line_final = first_line_text
        if canvas.stringWidth(first_line_text, "Helvetica", footer_font_size) > available_width_line1:
            parts = first_line_text.split(' | ')
            wrapped_lines = []
            current_line = ""
            for part in parts:
                separator = " | " if current_line else ""
                test_line = current_line + separator + part
                if canvas.stringWidth(test_line, "Helvetica", footer_font_size) <= available_width_line1:
                    current_line = test_line
                else:
                    if current_line:
                        wrapped_lines.append(current_line)
                    current_line = part
            if current_line:
                wrapped_lines.append(current_line)
            first_line_final = wrapped_lines[0] if wrapped_lines else first_line_text
        copyright_final = copyright_text
        if canvas.stringWidth(copyright_text, "Helvetica", footer_font_size) > available_width_line2:
            max_chars = int(available_width_line2 / (footer_font_size * 0.6))
            if len(copyright_text) > max_chars:
                copyright_final = copyright_text[:max_chars-3] + "..."
        footer_text_bottom = footer_bottom_padding
        footer_text_top = footer_text_bottom + line_height
        footer_line_y = footer_text_top + spacing_between_line_and_text
        canvas.setStrokeColor(colors.HexColor('#1e40af'))
        canvas.setLineWidth(footer_line_thickness)
        canvas.line(horizontal_padding, footer_line_y, page_size[0] - horizontal_padding, footer_line_y)
        canvas.setFont("Helvetica", footer_font_size)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(horizontal_padding, footer_text_top, first_line_final)
        canvas.drawString(horizontal_padding, footer_text_bottom, copyright_final)
        canvas.setFont("Helvetica-Bold", footer_font_size)
        canvas.setFillColor(colors.HexColor('#1e40af'))
        page_x = page_size[0] - horizontal_padding
        canvas.drawRightString(page_x, footer_text_bottom, page_text)
        canvas.restoreState()

    doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=task_management_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"}
    )

    """Generate professional Task Management Report PDF"""
    
    buffer = io.BytesIO()
    
    # Footer drawing function with two-line structure and proper alignment
    def draw_footer(canvas, doc):
        """Draw footer with company info and page number - two-line structure"""
        canvas.saveState()
        
        # Footer padding constants - consistent spacing
        footer_font_size = 8
        horizontal_padding = 30  # Consistent horizontal padding from edges
        footer_line_thickness = 0.5
        line_height = 11  # Vertical spacing between footer lines
        spacing_between_line_and_text = 8  # Space between footer line and text
        footer_bottom_padding = 15  # Padding from bottom of page
        
        # Build first line: Address | Website | Email | Contact
        first_line_parts = []
        if COMPANY_ADDRESS:
            first_line_parts.append(COMPANY_ADDRESS)
        if COMPANY_WEBSITE:
            first_line_parts.append(f"Website: {COMPANY_WEBSITE}")
        if COMPANY_EMAIL:
            first_line_parts.append(f"Email: {COMPANY_EMAIL}")
        if COMPANY_PHONE:
            first_line_parts.append(f"Contact: {COMPANY_PHONE}")
        
        first_line_text = " | ".join(first_line_parts)
        
        # Build second line: Copyright (left) + Page number (right)
        copyright_text = f"© {datetime.now().year} {COMPANY_NAME}. All rights reserved."
        page_text = f"Page {canvas.getPageNumber()}"
        
        # Set footer text style
        canvas.setFont("Helvetica", footer_font_size)
        canvas.setFillColor(colors.HexColor('#64748b'))
        
        # Calculate page number width for proper spacing
        canvas.setFont("Helvetica-Bold", footer_font_size)
        page_num_width = canvas.stringWidth(page_text, "Helvetica-Bold", footer_font_size)
        canvas.setFont("Helvetica", footer_font_size)
        
        # Calculate available width for first line (full width minus padding)
        available_width_line1 = A4[0] - (horizontal_padding * 2)
        
        # Calculate available width for second line (minus page number space)
        spacing_between_copyright_and_page = 15  # Space between copyright and page number
        available_width_line2 = A4[0] - (horizontal_padding * 2) - page_num_width - spacing_between_copyright_and_page
        
        # Wrap first line if needed (intelligent wrapping at separator points)
        first_line_final = first_line_text
        if canvas.stringWidth(first_line_text, "Helvetica", footer_font_size) > available_width_line1:
            # Split first line intelligently
            parts = first_line_text.split(' | ')
            wrapped_lines = []
            current_line = ""
            for part in parts:
                separator = " | " if current_line else ""
                test_line = current_line + separator + part
                if canvas.stringWidth(test_line, "Helvetica", footer_font_size) <= available_width_line1:
                    current_line = test_line
                else:
                    if current_line:
                        wrapped_lines.append(current_line)
                    current_line = part
            if current_line:
                wrapped_lines.append(current_line)
            # Use first wrapped line (or original if fits)
            first_line_final = wrapped_lines[0] if wrapped_lines else first_line_text
        
        # Wrap copyright text if needed for second line
        copyright_final = copyright_text
        if canvas.stringWidth(copyright_text, "Helvetica", footer_font_size) > available_width_line2:
            # Truncate copyright if too long (shouldn't happen normally)
            max_chars = int(available_width_line2 / (footer_font_size * 0.6))  # Approximate char width
            if len(copyright_text) > max_chars:
                copyright_final = copyright_text[:max_chars-3] + "..."
        
        # Calculate footer positions (from bottom up)
        # We always have exactly 2 lines now
        footer_text_bottom = footer_bottom_padding  # Bottom line (copyright + page)
        footer_text_top = footer_text_bottom + line_height  # Top line (address info)
        footer_line_y = footer_text_top + spacing_between_line_and_text  # Separator line above
        
        # Draw footer separator line with proper horizontal padding
        canvas.setStrokeColor(colors.HexColor('#1e40af'))
        canvas.setLineWidth(footer_line_thickness)
        canvas.line(horizontal_padding, footer_line_y, A4[0] - horizontal_padding, footer_line_y)
        
        # Draw first line (Address | Website | Email | Contact)
        canvas.setFont("Helvetica", footer_font_size)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(horizontal_padding, footer_text_top, first_line_final)
        
        # Draw second line: Copyright (left) + Page number (right)
        # Draw copyright text
        canvas.drawString(horizontal_padding, footer_text_bottom, copyright_final)
        
        # Draw page number (right-aligned)
        canvas.setFont("Helvetica-Bold", footer_font_size)
        canvas.setFillColor(colors.HexColor('#1e40af'))
        page_x = A4[0] - horizontal_padding
        canvas.drawRightString(page_x, footer_text_bottom, page_text)
        
        canvas.restoreState()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=50,
        bottomMargin=80  # Increased bottom margin for better footer spacing
    )
    
    # Container for elements
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Title style
    title_style = ParagraphStyle(
        'TaskReportTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Header style (centered "Report")
    header_style = ParagraphStyle(
        'ReportHeader',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=colors.HexColor('#3b82f6'),
        spaceAfter=15,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Info label style
    info_label_style = ParagraphStyle(
        'InfoLabel',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#64748b'),
        fontName='Helvetica-Bold',
        leftIndent=0
    )
    
    # Info value style
    info_value_style = ParagraphStyle(
        'InfoValue',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        fontName='Helvetica',
        leftIndent=0
    )
    
    # Title
    title = Paragraph("Task Management Report", title_style)
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    # Left side information table
    info_data = [
        ['Company Name:', COMPANY_NAME],
        ['Department Name:', department or 'All Departments'],
        ['Period:', period_label],
        ['Generated On:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        ['Generated By:', generated_by]
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eff6ff')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # Create cell styles for table (defined once, reused)
    header_cell_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.whitesmoke,
        fontName='Helvetica-Bold',
        leading=10,
        alignment=TA_CENTER
    )
    
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.black,
        fontName='Helvetica',
        leading=8,
        leftIndent=2,
        rightIndent=2,
        alignment=TA_LEFT
    )
    
    cell_style_center = ParagraphStyle(
        'TableCellCenter',
        parent=cell_style,
        alignment=TA_CENTER
    )
    
    # First pass: Collect all task data and determine which columns have data
    # Column definitions with their indices
    COL_TASK_ID = 0
    COL_TASK_NAME = 1
    COL_DESCRIPTION = 2
    COL_STATUS = 3
    COL_PRIORITY = 4
    COL_ASSIGNED_BY = 5
    COL_ASSIGNED_TO = 6
    COL_CREATED_DATE = 7
    COL_MODIFIED_DATE = 8
    COL_LAST_PASSED_TO = 9
    COL_COMPLETED_BY = 10
    
    # Track which columns have data (initialize with always-visible columns)
    columns_with_data = {
        COL_TASK_ID: True,      # Always show
        COL_TASK_NAME: True,    # Always show
        COL_DESCRIPTION: False,
        COL_STATUS: True,       # Always show
        COL_PRIORITY: True,     # Always show
        COL_ASSIGNED_BY: False,
        COL_ASSIGNED_TO: False,
        COL_CREATED_DATE: True, # Always show
        COL_MODIFIED_DATE: False,
        COL_LAST_PASSED_TO: False,
        COL_COMPLETED_BY: False,
    }
    
    # Escape HTML special characters for Paragraph (but preserve <br/> tags)
    def escape_html(text, preserve_breaks=False):
        if not text:
            return "N/A"
        text_str = str(text)
        if preserve_breaks:
            # Temporarily replace <br/> with a placeholder
            text_str = text_str.replace('<br/>', '___BR___')
            text_str = text_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            # Restore <br/> tags
            text_str = text_str.replace('___BR___', '<br/>')
        else:
            text_str = text_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return text_str
    
    # Collect all task data first to check for column data
    all_task_rows = []
    
    for task in tasks:
        # Get assigned_by user name
        assigned_by_name = "N/A"
        if task.assigned_by:
            assigned_by_user = db.query(User).filter(User.user_id == task.assigned_by).first()
            if assigned_by_user:
                assigned_by_name = assigned_by_user.name
        
        # Get assigned_to user name
        assigned_to_name = "N/A"
        if task.assigned_to:
            assigned_to_user = db.query(User).filter(User.user_id == task.assigned_to).first()
            if assigned_to_user:
                assigned_to_name = assigned_to_user.name
        
        # Get last_passed_to user name
        last_passed_to_name = "N/A"
        if task.last_passed_to:
            last_passed_to_user = db.query(User).filter(User.user_id == task.last_passed_to).first()
            if last_passed_to_user:
                last_passed_to_name = last_passed_to_user.name
        
        # Get completed_by from TaskHistory
        completed_by_name = "N/A"
        if task.status == str(TaskStatus.COMPLETED):
            # Find the history entry where status was changed to COMPLETED
            completion_history = db.query(TaskHistory).filter(
                TaskHistory.task_id == task.task_id,
                TaskHistory.action == TaskAction.STATUS_CHANGED
            ).order_by(TaskHistory.created_at.desc()).all()
            
            # Look for the entry that changed status to COMPLETED
            for hist in completion_history:
                if hasattr(hist, 'details') and hist.details:
                    try:
                        # Try to parse details (could be JSON string or dict)
                        if isinstance(hist.details, str):
                            details = json.loads(hist.details)
                        else:
                            details = hist.details
                        
                        # Check if this status change was to COMPLETED
                        if isinstance(details, dict) and details.get('to') == TaskStatus.COMPLETED.value:
                            completed_user = db.query(User).filter(User.user_id == hist.user_id).first()
                            if completed_user:
                                completed_by_name = completed_user.name
                                break
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        # If parsing fails, continue to next entry
                        pass
            
            # Fallback: if we didn't find it in details, use the last user who changed status
            if completed_by_name == "N/A" and completion_history:
                last_status_change = completion_history[0]
                completed_user = db.query(User).filter(User.user_id == last_status_change.user_id).first()
                if completed_user:
                    completed_by_name = completed_user.name
        
        # Format dates with line break for better wrapping (using <br/> for Paragraph)
        created_date = task.created_at.strftime('%Y-%m-%d<br/>%H:%M') if task.created_at else "N/A"
        
        # Get modified date (use last_passed_at if available, otherwise created_at)
        modified_date = "N/A"
        if task.last_passed_at:
            modified_date = task.last_passed_at.strftime('%Y-%m-%d<br/>%H:%M')
        elif task.created_at:
            modified_date = created_date
        
        # Use full text (will be wrapped by Paragraph)
        description = task.description or "N/A"
        task_name = task.title or "N/A"
        
        # Store row data (not as Paragraphs yet, so we can check for data)
        row_data = {
            COL_TASK_ID: str(task.task_id),
            COL_TASK_NAME: task_name,
            COL_DESCRIPTION: description,
            COL_STATUS: task.status or "N/A",
            COL_PRIORITY: task.priority or "Medium",
            COL_ASSIGNED_BY: assigned_by_name,
            COL_ASSIGNED_TO: assigned_to_name,
            COL_CREATED_DATE: created_date,
            COL_MODIFIED_DATE: modified_date,
            COL_LAST_PASSED_TO: last_passed_to_name,
            COL_COMPLETED_BY: completed_by_name
        }
        
        # Check which columns have data (not "N/A")
        if description != "N/A":
            columns_with_data[COL_DESCRIPTION] = True
        if assigned_by_name != "N/A":
            columns_with_data[COL_ASSIGNED_BY] = True
        if assigned_to_name != "N/A":
            columns_with_data[COL_ASSIGNED_TO] = True
        if modified_date != "N/A" and modified_date != created_date:
            columns_with_data[COL_MODIFIED_DATE] = True
        if last_passed_to_name != "N/A":
            columns_with_data[COL_LAST_PASSED_TO] = True
        if completed_by_name != "N/A":
            columns_with_data[COL_COMPLETED_BY] = True
        
        all_task_rows.append(row_data)
    
    # Build column mapping: which columns to include and their order
    column_order = []
    column_headers = []
    
    if columns_with_data[COL_TASK_ID]:
        column_order.append(COL_TASK_ID)
        column_headers.append(Paragraph('Task ID', header_cell_style))
    if columns_with_data[COL_TASK_NAME]:
        column_order.append(COL_TASK_NAME)
        column_headers.append(Paragraph('Task Name', header_cell_style))
    if columns_with_data[COL_DESCRIPTION]:
        column_order.append(COL_DESCRIPTION)
        column_headers.append(Paragraph('Description', header_cell_style))
    if columns_with_data[COL_STATUS]:
        column_order.append(COL_STATUS)
        column_headers.append(Paragraph('Status', header_cell_style))
    if columns_with_data[COL_PRIORITY]:
        column_order.append(COL_PRIORITY)
        column_headers.append(Paragraph('Priority', header_cell_style))
    if columns_with_data[COL_ASSIGNED_BY]:
        column_order.append(COL_ASSIGNED_BY)
        column_headers.append(Paragraph('Assigned By', header_cell_style))
    if columns_with_data[COL_ASSIGNED_TO]:
        column_order.append(COL_ASSIGNED_TO)
        column_headers.append(Paragraph('Assigned To', header_cell_style))
    if columns_with_data[COL_CREATED_DATE]:
        column_order.append(COL_CREATED_DATE)
        column_headers.append(Paragraph('Created Date', header_cell_style))
    if columns_with_data[COL_MODIFIED_DATE]:
        column_order.append(COL_MODIFIED_DATE)
        column_headers.append(Paragraph('Modified Date', header_cell_style))
    if columns_with_data[COL_LAST_PASSED_TO]:
        column_order.append(COL_LAST_PASSED_TO)
        column_headers.append(Paragraph('Last Passed To', header_cell_style))
    if columns_with_data[COL_COMPLETED_BY]:
        column_order.append(COL_COMPLETED_BY)
        column_headers.append(Paragraph('Completed By', header_cell_style))
    
    # Build task_data with header and only visible columns
    task_data = [column_headers]
    
    # Build rows with only visible columns
    for row_data in all_task_rows:
        row = []
        for col_idx in column_order:
            value = row_data[col_idx]
            
            # Determine cell style based on column type
            if col_idx in [COL_TASK_ID, COL_STATUS, COL_PRIORITY, COL_CREATED_DATE, COL_MODIFIED_DATE]:
                cell_style_to_use = cell_style_center
            else:
                cell_style_to_use = cell_style
            
            # Create Paragraph with proper formatting
            if col_idx in [COL_CREATED_DATE, COL_MODIFIED_DATE]:
                row.append(Paragraph(escape_html(value, preserve_breaks=True), cell_style_to_use))
            else:
                row.append(Paragraph(escape_html(value), cell_style_to_use))
        
        task_data.append(row)
    
    # Create task table with improved formatting
    # Calculate column widths dynamically based on visible columns
    total_width = A4[0] - 60  # Total available width
    num_visible_cols = len(column_order)
    
    # Base width percentages for each column type (when all columns visible)
    base_widths = {
        COL_TASK_ID: 0.05,
        COL_TASK_NAME: 0.13,
        COL_DESCRIPTION: 0.27,
        COL_STATUS: 0.08,
        COL_PRIORITY: 0.08,
        COL_ASSIGNED_BY: 0.10,
        COL_ASSIGNED_TO: 0.10,
        COL_CREATED_DATE: 0.08,
        COL_MODIFIED_DATE: 0.08,
        COL_LAST_PASSED_TO: 0.10,
        COL_COMPLETED_BY: 0.7,
    }
    
    # Calculate total base width for visible columns
    total_base_width = sum(base_widths[col_idx] for col_idx in column_order)
    
    # Calculate column widths proportionally
    col_widths = []
    for col_idx in column_order:
        # Proportionally adjust width based on visible columns
        base_width = base_widths[col_idx]
        # Scale to ensure columns fill available width
        proportional_width = (base_width / total_base_width) if total_base_width > 0 else (1.0 / num_visible_cols)
        col_widths.append(total_width * proportional_width)
    
    # Build table style with dynamic alignment based on visible columns
    table_style = [
        # Header row - improved styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('LEFTPADDING', (0, 0), (-1, 0), 4),
        ('RIGHTPADDING', (0, 0), (-1, 0), 4),
        
        # Data rows - improved padding and alignment
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),  # Default left alignment
        ('VALIGN', (0, 1), (-1, -1), 'TOP'),    # Top align for wrapped text
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 1), (-1, -1), 4),
        ('RIGHTPADDING', (0, 1), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        
        # Alternating row colors for better readability
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        
        # Row height - allow rows to expand for wrapped text
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#1e40af')),
    ]
    
    # Add center alignment for specific column types dynamically
    center_aligned_cols = [COL_TASK_ID, COL_STATUS, COL_PRIORITY, COL_CREATED_DATE, COL_MODIFIED_DATE]
    for col_idx in center_aligned_cols:
        if col_idx in column_order:
            col_position = column_order.index(col_idx)
            table_style.append(('ALIGN', (col_position, 1), (col_position, -1), 'CENTER'))
    
    task_table = Table(task_data, colWidths=col_widths, repeatRows=1)
    task_table.setStyle(TableStyle(table_style))
    
    elements.append(task_table)
    
    # Build PDF with custom footer
    doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
    
    # Prepare response
    buffer.seek(0)
    filename = f"task_management_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
