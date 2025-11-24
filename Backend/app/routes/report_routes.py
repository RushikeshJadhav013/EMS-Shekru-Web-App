"""
Report Routes - Employee Performance and Department Metrics
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status as http_status
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timedelta
from typing import Optional, List
import traceback

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.attendance import Attendance
from app.db.models.task import Task
from app.dependencies import get_current_user, require_roles
from app.enums import RoleEnum, TaskStatus

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/employee-performance")
def get_employee_performance(
    month: int = Query(..., ge=0, le=11, description="Month (0-11)"),
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
    
    try:
        # Calculate date range for the month
        # Frontend sends 0-indexed month (0-11), convert to 1-indexed (1-12)
        actual_month = month + 1
        
        start_date = datetime(year, actual_month, 1)
        # Calculate end date (first day of next month)
        if actual_month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, actual_month + 1, 1)
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
        # Base query for active employees
        query = db.query(User).filter(User.is_active == True)
        
        # Apply filters
        if department and department != 'all':
            query = query.filter(User.department == department)
        
        if employee_id:
            query = query.filter(User.employee_id == employee_id)
        
        employees = query.order_by(User.name).all()
        
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
    month: int = Query(..., ge=0, le=11, description="Month (0-11)"),
    year: int = Query(..., description="Year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get department-wise performance metrics.
    Aggregates employee data by department.
    """
    
    try:
        # Calculate date range
        # Frontend sends 0-indexed month (0-11), convert to 1-indexed (1-12)
        actual_month = month + 1
        
        start_date = datetime(year, actual_month, 1)
        # Calculate end date (first day of next month)
        if actual_month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, actual_month + 1, 1)
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
    
    # Get all departments with active employees
    departments = db.query(User.department).filter(
        User.is_active == True,
        User.department.isnot(None),
        User.department != ''
    ).distinct().all()
    
    results = []
    for (dept_name,) in departments:
        if not dept_name:
            continue
        
        # Get employees in department
        dept_employees = db.query(User).filter(
            User.department == dept_name,
            User.is_active == True
        ).all()
        
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
    month: int = Query(..., ge=0, le=11, description="Month (0-11)"),
    year: int = Query(..., description="Year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get executive summary with top performers and key metrics.
    """
    
    # Calculate date range
    # Frontend sends 0-indexed month (0-11), convert to 1-indexed (1-12)
    actual_month = month + 1
    
    try:
        start_date = datetime(year, actual_month, 1)
        # Calculate end date (first day of next month)
        if actual_month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, actual_month + 1, 1)
    except ValueError as e:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date: month={month}, year={year}. Error: {str(e)}"
        )
    
    # Get all active employees
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate working days
    total_working_days = 0
    current = start_date
    while current < end_date:
        if current.weekday() < 5:
            total_working_days += 1
        current += timedelta(days=1)
    
    # Calculate metrics for each employee
    employee_scores = []
    total_performance = 0
    
    for emp in employees:
        # Attendance score
        attendance_count = db.query(Attendance).filter(
            Attendance.user_id == emp.user_id,
            Attendance.check_in >= start_date,
            Attendance.check_in < end_date
        ).count()
        attendance_score = (attendance_count / total_working_days) * 100 if total_working_days > 0 else 0
        attendance_score = min(attendance_score, 100)
        
        # Task completion
        total_tasks = db.query(Task).filter(
            Task.assigned_to == emp.user_id
        ).count()
        
        completed_tasks = db.query(Task).filter(
            Task.assigned_to == emp.user_id,
            Task.status == str(TaskStatus.COMPLETED)
        ).count()
        
        task_score = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        
        # Overall score (average of attendance and tasks)
        overall_score = (attendance_score + task_score) / 2
        
        employee_scores.append({
            "name": emp.name,
            "score": round(overall_score),
            "department": emp.department
        })
        
        total_performance += overall_score
    
    # Find top performer
    top_performer = max(employee_scores, key=lambda x: x['score']) if employee_scores else {"name": "N/A", "score": 0}
    
    # Calculate average performance
    avg_performance = round(total_performance / len(employees)) if employees else 0
    
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
        "topPerformer": top_performer,
        "avgPerformance": avg_performance,
        "totalTasksCompleted": total_tasks_completed,
        "bestDepartment": best_dept,
        "keyFindings": [
            f"Average employee performance is {avg_performance}%",
            f"Top performer: {top_performer['name']} with {top_performer['score']}% score",
            f"Total tasks completed: {total_tasks_completed}",
            f"Best performing department: {best_dept['name']} ({best_dept['score']}%)"
        ],
        "recommendations": [
            "Recognize top performers to maintain motivation",
            "Provide additional support for underperforming employees",
            "Share best practices from high-performing departments",
            "Review task allocation for better efficiency"
        ],
        "actionItems": [
            "Schedule performance review meetings",
            "Plan recognition program for top performers",
            "Conduct training needs assessment",
            "Implement weekly progress tracking"
        ]
    }


@router.get("/departments")
def get_departments_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get list of all departments with active employees"""
    departments = db.query(User.department).filter(
        User.is_active == True,
        User.department.isnot(None),
        User.department != ''
    ).distinct().order_by(User.department).all()
    
    return {"departments": [dept[0] for dept in departments if dept[0]]}
