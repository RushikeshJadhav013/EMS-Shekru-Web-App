"""
Report Routes - Employee Performance and Department Metrics
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status as http_status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timedelta
from typing import Optional, List
import traceback
import io
import csv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.attendance import Attendance
from app.db.models.task import Task
from app.db.models.leave import Leave
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
    
    try:
        # Parse dates
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Get employees
        query = db.query(User).filter(User.is_active == True)
        if employee_id:
            query = query.filter(User.employee_id == employee_id)
        employees = query.all()
        
        if not employees:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="No employees found"
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
    
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0e7ff')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # Employee performance summary
    for emp in data:
        # Employee header
        emp_heading = Paragraph(f"<b>{emp['name']}</b> ({emp['employee_id']})", heading_style)
        elements.append(emp_heading)
        
        # Employee details
        emp_details = [
            ['Department:', emp['department'], 'Designation:', emp['designation']],
            ['Email:', emp['email'], 'Role:', emp['role']],
        ]
        
        details_table = Table(emp_details, colWidths=[1.2*inch, 2*inch, 1.2*inch, 2*inch])
        details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
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
        
        metrics_table = Table(metrics_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
        ]))
        
        elements.append(metrics_table)
        
        # Leave type breakdown
        if emp['leave_types']:
            elements.append(Spacer(1, 10))
            leave_heading = Paragraph("<b>Leave Type Breakdown:</b>", styles['Normal'])
            elements.append(leave_heading)
            
            leave_data = [['Leave Type', 'Count']]
            for leave_type, count in emp['leave_types'].items():
                leave_data.append([leave_type.title(), str(count)])
            
            leave_table = Table(leave_data, colWidths=[3*inch, 1*inch])
            leave_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
            ]))
            
            elements.append(leave_table)
        
        # Performance score highlight
        elements.append(Spacer(1, 10))
        score_color = colors.green if emp['performance_score'] >= 75 else colors.orange if emp['performance_score'] >= 60 else colors.red
        score_data = [['Overall Performance Score', f"{emp['performance_score']}%"]]
        score_table = Table(score_data, colWidths=[4*inch, 2*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), score_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
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
