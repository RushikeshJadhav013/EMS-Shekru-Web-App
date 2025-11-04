from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime,timedelta
from app.db.models.attendance import Attendance
from app.db.models.user import User # Import User model
import csv 
import io 
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet 


def check_in(db: Session, user_id: int, gps_location: str = None, selfie: str = None):
    try:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Check for existing attendance record today
        attendance = (
            db.query(Attendance)
            .filter(
                Attendance.user_id == user_id, 
                Attendance.check_in >= today_start,
                Attendance.check_out.is_(None)  # Only consider open check-ins
            )
            .order_by(Attendance.check_in.desc())
            .first()
        )
        
        if attendance:
            # Update existing check-in
            attendance.check_in = datetime.utcnow()
            attendance.gps_location = gps_location or attendance.gps_location
            attendance.selfie = selfie or attendance.selfie
        else:
            # Create new check-in
            attendance = Attendance(
                user_id=user_id,
                check_in=datetime.utcnow(),
                gps_location=gps_location,
                selfie=selfie,
                total_hours=0.0  # Initialize total_hours
            )
            db.add(attendance)
        
        db.commit()
        db.refresh(attendance)
        return attendance
        
    except Exception as e:
        db.rollback()
        raise e

def check_out(db: Session, user_id: int, gps_location: str = None, selfie: str = None):
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    attendance = (
        db.query(Attendance)
        .filter(Attendance.user_id == user_id, Attendance.check_in >= today_start)
        .first()
    )
    if not attendance:
        return None

    # Update checkout and calculate total hours
    now = datetime.utcnow()
    if attendance.check_out:
        # Add hours from previous checkout to now
        delta = now - attendance.check_out
    else:
        # First checkout today
        delta = now - attendance.check_in

    attendance.check_out = now
    attendance.total_hours += delta.total_seconds() / 3600  # hours
    attendance.gps_location = gps_location or attendance.gps_location
    attendance.selfie = selfie or attendance.selfie

    db.commit()
    db.refresh(attendance)
    return attendance

def list_attendance(db: Session, user_id: int):
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    return (
        db.query(Attendance)
        .filter(Attendance.user_id == user_id, Attendance.check_in >= six_months_ago)
        .order_by(Attendance.check_in.desc())
        .all()
    )

def total_present_today(db: Session):
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    return db.query(Attendance).filter(Attendance.check_in >= today_start, Attendance.check_in < today_end).count()

def get_all_attendance(db: Session, department: str = None):
    """Get all attendance records, optionally filtered by department"""
    query = db.query(Attendance, User.name, User.department, User.employee_id).join(User, Attendance.user_id == User.user_id)
    
    if department:
        query = query.filter(User.department == department)
    
    return query.order_by(Attendance.check_in.desc()).all()

def get_today_attendance_status(db: Session, department: str = None):
    """Get today's attendance status for all employees"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get all users
    users_query = db.query(User)
    if department:
        users_query = users_query.filter(User.department == department)
    
    all_users = users_query.all()
    
    # Get today's attendance
    attendance_records = (
        db.query(Attendance)
        .filter(Attendance.check_in >= today_start)
        .all()
    )
    
    # Create a map of user_id to attendance
    attendance_map = {att.user_id: att for att in attendance_records}
    
    # Build result
    result = []
    for user in all_users:
        attendance = attendance_map.get(user.user_id)
        result.append({
            "user_id": user.user_id,
            "employee_id": user.employee_id,
            "name": user.name,
            "department": user.department,
            "designation": user.designation,
            "has_checked_in": attendance is not None,
            "check_in": attendance.check_in if attendance else None,
            "check_out": attendance.check_out if attendance else None,
            "total_hours": attendance.total_hours if attendance else 0.0,
            "status": "Present" if attendance else "Absent"
        })
    
    return result

def get_today_attendance_records(db: Session):
    """Get today's attendance records with user details for manager view"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Join attendance with user to get employee details
    records = (
        db.query(Attendance, User)
        .join(User, Attendance.user_id == User.user_id)
        .filter(Attendance.check_in >= today_start, Attendance.check_in < today_end)
        .all()
    )
    
    result = []
    for attendance, user in records:
        # Determine status based on check-in time
        check_in_time = attendance.check_in.time() if attendance.check_in else None
        status = "present"
        
        # Late if checked in after 9:30 AM
        if check_in_time and check_in_time.hour >= 9 and (check_in_time.hour > 9 or check_in_time.minute > 30):
            status = "late"
        
        result.append({
            "id": attendance.attendance_id,
            "userId": user.user_id,
            "userName": user.name,
            "userEmail": user.email,
            "department": user.department or "N/A",
            "date": attendance.check_in.strftime("%Y-%m-%d") if attendance.check_in else None,
            "checkInTime": attendance.check_in.isoformat() if attendance.check_in else None,  # Return ISO datetime for proper timezone handling
            "checkOutTime": attendance.check_out.isoformat() if attendance.check_out else None,  # Return ISO datetime for proper timezone handling
            "workHours": round(attendance.total_hours or 0, 2),
            "status": status,
            "checkInLocation": {
                "address": attendance.gps_location or "N/A"
            }
        })
    
    return result

def get_attendance_summary(db: Session):
    """Get attendance summary with statistics"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Total employees
    total_employees = db.query(User).count()
    
    # Present today (checked in today)
    present_today = db.query(Attendance).filter(
        Attendance.check_in >= today_start,
        Attendance.check_in < today_end
    ).count()
    
    # Late arrivals (checked in after 9:30 AM)
    late_today = db.query(Attendance).filter(
        Attendance.check_in >= today_start,
        Attendance.check_in < today_end
    ).filter(
        func.extract('hour', Attendance.check_in) * 60 + func.extract('minute', Attendance.check_in) > 9 * 60 + 30
    ).count()
    
    # Early departures (checked out before 6:00 PM)
    early_today = db.query(Attendance).filter(
        Attendance.check_in >= today_start,
        Attendance.check_in < today_end,
        Attendance.check_out.isnot(None)
    ).filter(
        func.extract('hour', Attendance.check_out) * 60 + func.extract('minute', Attendance.check_out) < 18 * 60
    ).count()
    
    # Absent today
    absent_today = total_employees - present_today
    
    return {
        "total_employees": total_employees,
        "present_today": present_today,
        "late_today": late_today,
        "early_today": early_today,
        "absent_today": absent_today
    }

# ✅ Export Attendance to CSV
def export_attendance_csv(db: Session, user_id: int = None, start_date: datetime = None, end_date: datetime = None, employee_id: str = None):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Attendance ID", "Employee ID", "Name", "Department", "Check In", "Check Out", "Total Hours (hrs)", "GPS", "Selfie"])

    # Modify the query to join with User and fetch name, department, and employee_id
    query = db.query(Attendance, User.name, User.department, User.employee_id).join(User, Attendance.user_id == User.user_id)
    
    # Apply filters
    if user_id:
        query = query.filter(Attendance.user_id == user_id)
    
    if employee_id:
        query = query.filter(User.employee_id == employee_id)
    
    if start_date:
        query = query.filter(Attendance.check_in >= start_date)
    
    if end_date:
        # Add one day to include the entire end_date
        end_date_inclusive = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        query = query.filter(Attendance.check_in <= end_date_inclusive)

    for a, name, department, emp_id in query.order_by(Attendance.check_in.desc()).all():
        writer.writerow([
            a.attendance_id,
            emp_id or a.user_id,  # Use employee_id if available, fallback to user_id
            name,
            department or "",
            a.check_in.strftime("%Y-%m-%d %H:%M:%S") if a.check_in else "",
            a.check_out.strftime("%Y-%m-%d %H:%M:%S") if a.check_out else "",
            round(a.total_hours or 0, 2),
            a.gps_location or "",
            a.selfie or ""
        ])

    output.seek(0)
    return output


# ✅ Export Attendance to PDF
def export_attendance_pdf(db: Session, user_id: int = None, start_date: datetime = None, end_date: datetime = None, employee_id: str = None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    data = [["Attendance ID", "Employee ID", "Name", "Department", "Check In", "Check Out", "Total Hours"]]
    # Modify the query to join with User and fetch name, department, and employee_id
    query = db.query(Attendance, User.name, User.department, User.employee_id).join(User, Attendance.user_id == User.user_id)
    
    # Apply filters
    if user_id:
        query = query.filter(Attendance.user_id == user_id)
    
    if employee_id:
        query = query.filter(User.employee_id == employee_id)
    
    if start_date:
        query = query.filter(Attendance.check_in >= start_date)
    
    if end_date:
        # Add one day to include the entire end_date
        end_date_inclusive = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        query = query.filter(Attendance.check_in <= end_date_inclusive)

    for a, name, department, emp_id in query.order_by(Attendance.check_in.desc()).all():
        data.append([
            a.attendance_id,
            emp_id or str(a.user_id),  # Use employee_id if available, fallback to user_id
            name,
            department or "",
            a.check_in.strftime("%Y-%m-%d %H:%M:%S") if a.check_in else "",
            a.check_out.strftime("%Y-%m-%d %H:%M:%S") if a.check_out else "",
            f"{round(a.total_hours or 0, 2)} hrs"
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))

    # Build title with date range info
    title = "Employee Attendance Report"
    if start_date or end_date:
        date_str = ""
        if start_date:
            date_str += f"From {start_date.strftime('%Y-%m-%d')}"
        if end_date:
            if date_str:
                date_str += f" to {end_date.strftime('%Y-%m-%d')}"
            else:
                date_str += f"Until {end_date.strftime('%Y-%m-%d')}"
        title += f" - {date_str}"
    
    elements.append(Paragraph(title, styles['Title']))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer