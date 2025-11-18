from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

from app.db.models.attendance import Attendance
from app.db.models.user import User  # Import User model
from app.db.models.office_timing import OfficeTiming
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

def _normalize_department_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _build_office_timing_cache(db: Session) -> Tuple[Optional[OfficeTiming], Dict[str, OfficeTiming]]:
    records = (
        db.query(OfficeTiming)
        .filter(OfficeTiming.is_active.is_(True))
        .order_by(OfficeTiming.updated_at.desc())
        .all()
    )
    
    global_entry: Optional[OfficeTiming] = None
    department_entries: Dict[str, OfficeTiming] = {}

    for entry in records:
        dept_key = _normalize_department_value(entry.department)
        if dept_key is None:
            if global_entry is None or (
                entry.updated_at and (global_entry.updated_at is None or entry.updated_at > global_entry.updated_at)
            ):
                global_entry = entry
        else:
            existing = department_entries.get(dept_key)
            if existing is None or (
                entry.updated_at and (existing.updated_at is None or entry.updated_at > existing.updated_at)
            ):
                department_entries[dept_key] = entry

    return global_entry, department_entries


def _resolve_office_timing(
    db: Session,
    department: Optional[str],
    cache: Optional[Tuple[Optional[OfficeTiming], Dict[str, OfficeTiming]]] = None,
) -> Optional[OfficeTiming]:
    if cache is None:
        cache = _build_office_timing_cache(db)
    global_entry, department_entries = cache
    dept_key = _normalize_department_value(department)
    if dept_key and dept_key in department_entries:
        return department_entries[dept_key]
    return global_entry


def _evaluate_attendance_status(
    check_in: Optional[datetime],
    check_out: Optional[datetime],
    timing: Optional[OfficeTiming],
) -> Dict[str, str | None]:
    scheduled_start = timing.start_time.strftime("%H:%M") if timing else None
    scheduled_end = timing.end_time.strftime("%H:%M") if timing else None

    if not check_in:
        return {
            "status": "absent",
            "check_in_status": "absent",
            "check_out_status": "absent",
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
        }

    late = False
    early = False
    check_in_status = "on_time"
    check_out_status = "pending"

    if timing:
        start_dt = datetime.combine(check_in.date(), timing.start_time)
        if timing.check_in_grace_minutes:
            start_dt += timedelta(minutes=timing.check_in_grace_minutes)
        if check_in > start_dt:
            late = True
            check_in_status = "late"

    if check_out:
        check_out_status = "on_time"
        if timing:
            ref_date = check_out.date() if check_out else check_in.date()
            end_dt = datetime.combine(ref_date, timing.end_time)
            if timing.check_out_grace_minutes:
                end_dt -= timedelta(minutes=timing.check_out_grace_minutes)
            if check_out < end_dt:
                early = True
                check_out_status = "early"
    else:
        check_out_status = "pending"

    if not timing:
        check_in_status = "on_time"
        check_out_status = "on_time" if check_out else "pending"

    status = "present"
    if late:
        status = "late"

    return {
        "status": status,
        "check_in_status": check_in_status,
        "check_out_status": check_out_status,
        "scheduled_start": scheduled_start,
        "scheduled_end": scheduled_end,
    }


def get_today_attendance_status(db: Session, department: str = None):
    records_query = (
        db.query(
            Attendance,
            User.name,
            User.department,
            User.employee_id,
            User.email,
        )
        .join(User, Attendance.user_id == User.user_id)
    )

    if department:
        records_query = records_query.filter(User.department == department)

    records = records_query.order_by(Attendance.check_in.desc()).all()

    result = []
    timing_cache = _build_office_timing_cache(db)
    for att, name, dept, emp_id, email in records:
        evaluation = _evaluate_attendance_status(att.check_in, att.check_out, _resolve_office_timing(db, dept, timing_cache))
        payload = {
            "attendance_id": att.attendance_id,
            "user_id": att.user_id,
            "employee_id": emp_id,
            "name": name,
            "department": dept,
            "check_in": att.check_in.isoformat() if att.check_in else None,
            "check_out": att.check_out.isoformat() if att.check_out else None,
            "total_hours": att.total_hours,
            "email": email,
            "status": evaluation["status"],
            "checkInStatus": evaluation["check_in_status"],
            "checkOutStatus": evaluation["check_out_status"],
            "scheduledStart": evaluation["scheduled_start"],
            "scheduledEnd": evaluation["scheduled_end"],
        }
        result.append(payload)
    
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
    timing_cache = _build_office_timing_cache(db)
    for attendance, user in records:
        evaluation = _evaluate_attendance_status(
            attendance.check_in, attendance.check_out, _resolve_office_timing(db, user.department, timing_cache)
        )
        
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
            "status": evaluation["status"],
            "checkInStatus": evaluation["check_in_status"],
            "checkOutStatus": evaluation["check_out_status"],
            "scheduledStart": evaluation["scheduled_start"],
            "scheduledEnd": evaluation["scheduled_end"],
            "checkInLocation": {
                "address": attendance.gps_location or "N/A"
            }
        })
    
    return result

def get_attendance_summary(db: Session):
    """Get attendance summary with statistics"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    total_employees = db.query(User).count()
    
    records = (
        db.query(Attendance, User)
        .join(User, Attendance.user_id == User.user_id)
        .filter(Attendance.check_in >= today_start, Attendance.check_in <= today_end)
        .all()
    )

    timing_cache = _build_office_timing_cache(db)
    present_user_ids = set()
    late_arrivals = 0
    early_departures = 0
    work_durations: list[float] = []

    for attendance, user in records:
        present_user_ids.add(user.user_id)
        evaluation = _evaluate_attendance_status(
            attendance.check_in, attendance.check_out, _resolve_office_timing(db, user.department, timing_cache)
        )
        if evaluation["check_in_status"] == "late":
            late_arrivals += 1
        if evaluation["check_out_status"] == "early":
            early_departures += 1
        if attendance.check_in and attendance.check_out:
            duration = attendance.check_out - attendance.check_in
            work_durations.append(duration.total_seconds() / 3600.0)

    present_today = len(present_user_ids)
    absent_today = max(total_employees - present_today, 0)
    average_work_hours = sum(work_durations) / len(work_durations) if work_durations else 0.0

    summary = {
        "total_employees": total_employees,
        "present_today": present_today,
        "late_arrivals": late_arrivals,
        "early_departures": early_departures,
        "absent_today": absent_today,
        "average_work_hours": round(average_work_hours, 2),
    }

    return summary

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