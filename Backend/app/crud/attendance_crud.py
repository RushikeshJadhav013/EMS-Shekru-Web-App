from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from calendar import monthrange
from datetime import date

from app.db.models.attendance import Attendance
from app.db.models.user import User  # Import User model
from app.db.models.office_timing import OfficeTiming
from app.utils.timezone import now_ist, get_today_bounds_ist
import csv
import io
import os
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from app.config.company_config import (
    COMPANY_NAME, COMPANY_ADDRESS, COMPANY_PHONE, COMPANY_EMAIL, COMPANY_WEBSITE
)

def check_in(db: Session, user_id: int, gps_location: str = None, selfie: str = None):
    try:
        today_start, today_end = get_today_bounds_ist()
        
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
            attendance.check_in = now_ist()
            attendance.gps_location = gps_location or attendance.gps_location
            attendance.selfie = selfie or attendance.selfie
        else:
            attendance = Attendance(
                user_id=user_id,
                check_in=now_ist(),
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
    today_start, today_end = get_today_bounds_ist()
    attendance = (
        db.query(Attendance)
        .filter(Attendance.user_id == user_id, Attendance.check_in >= today_start)
        .first()
    )
    if not attendance:
        return None

    # Update checkout and calculate total hours (IST naive)
    now_ist_value = now_ist()
    if attendance.check_out:
        # Add hours from previous checkout to now
        delta = now_ist_value - attendance.check_out
    else:
        # First checkout today
        delta = now_ist_value - attendance.check_in

    attendance.check_out = now_ist_value
    attendance.total_hours += delta.total_seconds() / 3600  # hours
    attendance.gps_location = gps_location or attendance.gps_location
    attendance.selfie = selfie or attendance.selfie

    db.commit()
    db.refresh(attendance)
    return attendance

def list_attendance(db: Session, user_id: int):
    six_months_ago = now_ist() - timedelta(days=180)
    return (
        db.query(Attendance)
        .filter(Attendance.user_id == user_id, Attendance.check_in >= six_months_ago)
        .order_by(Attendance.check_in.desc())
        .all()
    )

def total_present_today(db: Session):
    today_start, today_end = get_today_bounds_ist()
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


def _to_local_timezone(dt: Optional[datetime]) -> Optional[datetime]:
    return dt


def _evaluate_attendance_status(
    check_in: Optional[datetime],
    check_out: Optional[datetime],
    timing: Optional[OfficeTiming],
) -> Dict[str, str | None]:
    local_check_in = _to_local_timezone(check_in)
    local_check_out = _to_local_timezone(check_out)

    scheduled_start = timing.start_time.strftime("%H:%M") if timing else None
    scheduled_end = timing.end_time.strftime("%H:%M") if timing else None

    if not local_check_in:
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
        start_dt = datetime.combine(local_check_in.date(), timing.start_time)
        if timing.check_in_grace_minutes:
            start_dt += timedelta(minutes=timing.check_in_grace_minutes)
        if local_check_in > start_dt:
            late = True
            check_in_status = "late"

    if local_check_out:
        check_out_status = "on_time"
        if timing:
            ref_date = local_check_out.date() if local_check_out else local_check_in.date()
            end_dt = datetime.combine(ref_date, timing.end_time)
            if timing.check_out_grace_minutes:
                end_dt -= timedelta(minutes=timing.check_out_grace_minutes)
            if local_check_out < end_dt:
                early = True
                check_out_status = "early"
    else:
        check_out_status = "pending"

    if not timing:
        check_in_status = "on_time"
        check_out_status = "on_time" if local_check_out else "pending"

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
    today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
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
    today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
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
def export_attendance_csv(
    db: Session,
    user_id: int = None,
    start_date: datetime = None,
    end_date: datetime = None,
    employee_id: str = None,
    department: Optional[str] = None,
):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Attendance ID",
        "Employee ID",
        "Name",
        "Department",
        "Check In",
        "Check Out",
        "Total Hours (hrs)",
        "GPS",
        "Selfie",
        "Work Summary",
        "Work Report",
    ])

    # Modify the query to join with User and fetch name, department, and employee_id
    query = db.query(Attendance, User.name, User.department, User.employee_id).join(User, Attendance.user_id == User.user_id)
    
    # Apply filters
    if user_id:
        query = query.filter(Attendance.user_id == user_id)
    
    if employee_id:
        query = query.filter(User.employee_id == employee_id)
    
    if department:
        query = query.filter(func.lower(User.department) == department.strip().lower())
    
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
            a.selfie or "",
            (a.work_summary or "").replace("\n", " ").strip(),
            a.work_report or "",
        ])

    output.seek(0)
    return output


# ✅ Export Attendance to PDF
def export_attendance_pdf(
    db: Session,
    user_id: int = None,
    start_date: datetime = None,
    end_date: datetime = None,
    employee_id: str = None,
    department: Optional[str] = None,
    generated_by: Optional[str] = None,
):
    buffer = io.BytesIO()
    # Use A4 landscape and tight, even margins for a clean, unified look (like Leave Report)
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
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

    # Title (centered) but minimal styling
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.black,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    elements.append(Paragraph("Attendance Report", title_style))
    elements.append(Spacer(1, 12))
    # Left-aligned key-value header (labels on left, values on right)
    period_text = f"{start_date.strftime('%Y-%m-%d') if start_date else 'Any'} to {end_date.strftime('%Y-%m-%d') if end_date else 'Any'}"
    generated_on = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    info_data = [
        ['Company Name', COMPANY_NAME or ''],
        ['Department', department or 'Any'],
        ['Period', period_text],
        ['Generated', generated_on],
        ['Generated By', generated_by or ''],
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
    # Footer drawing function, simplest style (matches Leave Report)
    def draw_footer(canvas, doc_obj):
        canvas.saveState()
        footer_font_size = 8
        horizontal_padding = 30
        footer_line_thickness = 0.5
        line_height = 11
        spacing_between_line_and_text = 8
        footer_bottom_padding = 15
        page_size = landscape(A4)

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

        # --- Copy Leave Report wrapping/truncation and styling
        canvas.setFont("Helvetica", footer_font_size)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.setFont("Helvetica-Bold", footer_font_size)
        page_num_width = canvas.stringWidth(page_text, "Helvetica-Bold", footer_font_size)
        canvas.setFont("Helvetica", footer_font_size)
        available_width_line1 = page_size[0] - (horizontal_padding * 2)
        spacing_between_copyright_and_page = 15
        available_width_line2 = page_size[0] - (horizontal_padding * 2) - page_num_width - spacing_between_copyright_and_page

        # Wrap first line intelligently
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

        # Truncate copyright if needed
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

    data = [
        [
            "Attendance ID",
            "Employee ID",
            "Name",
            "Department",
            "Check In",
            "Check Out",
            "Total Hours",
            "Work Summary",
            "Work Report",
        ]
    ]
    # Modify the query to join with User and fetch name, department, and employee_id
    query = db.query(Attendance, User.name, User.department, User.employee_id).join(User, Attendance.user_id == User.user_id)
    
    # Apply filters
    if user_id:
        query = query.filter(Attendance.user_id == user_id)
    
    if employee_id:
        query = query.filter(User.employee_id == employee_id)
    
    if department:
        query = query.filter(func.lower(User.department) == department.strip().lower())
    
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
            f"{round(a.total_hours or 0, 2)} hrs",
            (a.work_summary or "").strip(),
            a.work_report or "",
        ])

    # --- Reproduce Leave report’s dynamic column, style, truncation rules ---
    headers = [
        'Attendance ID', 'Employee ID', 'Name', 'Department', 'Check In', 'Check Out', 'Total Hours', 'Work Summary', 'Work Report'
    ]
    num_cols = len(headers)
    data_rows = []
    for a, emp_id, name, dept in query.order_by(Attendance.check_in.desc()).all():
        data_rows.append([
            str(a.attendance_id),
            emp_id or str(a.user_id),
            name or "",
            dept or "",
            a.check_in.strftime("%Y-%m-%d %H:%M:%S") if a.check_in else "",
            a.check_out.strftime("%Y-%m-%d %H:%M:%S") if a.check_out else "",
            str(round(a.total_hours or 0, 2)),
            (a.work_summary or "").strip(),
            a.work_report or "",
        ])
    data = [headers] + data_rows
    columns_with_data = [False] * num_cols
    essential = {0, 1, 2}
    for i in essential:
        columns_with_data[i] = True
    for row in data_rows:
        for idx, cell in enumerate(row):
            text = "" if cell is None else str(cell).strip()
            if text and text.lower() not in ("n/a", "na", "-"):
                columns_with_data[idx] = True
    visible_cols = [i for i, present in enumerate(columns_with_data) if present]
    visible_count = len(visible_cols) if visible_cols else num_cols
    total_width = page_size[0] - (left_margin + right_margin)
    col_widths = [total_width / visible_count] * visible_count
    from reportlab.lib.styles import ParagraphStyle
    styles_tbl = getSampleStyleSheet()
    header_style = ParagraphStyle('Header', parent=styles_tbl['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.black, alignment=TA_CENTER)
    cell_style = ParagraphStyle('Cell', parent=styles_tbl['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.black, alignment=TA_LEFT)
    cell_center = ParagraphStyle('CellCenter', parent=cell_style, alignment=TA_CENTER)
    def truncate_text(text: str, max_width_pts: float, font_size: int = 9) -> str:
        avg_char_width = font_size * 0.55
        max_chars = max(1, int(max_width_pts / avg_char_width))
        t = str(text)
        if len(t) > max_chars:
            return t[:max_chars-3] + "..."
        return t
    table_rows = []
    header_cells = [truncate_text(headers[i], col_widths[pos], font_size=10) for pos, i in enumerate(visible_cols)]
    table_rows.append(header_cells)
    for r in data_rows:
        row_cells = []
        for pos, idx in enumerate(visible_cols):
            raw = "" if r[idx] is None else str(r[idx])
            text = truncate_text(raw, col_widths[pos], font_size=9)
            text = text.replace("\n", " ").replace("\r", " ")
            row_cells.append(text)
        table_rows.append(row_cells)
    table = Table(table_rows, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('LEFTPADDING', (0, 1), (-1, -1), 6),
        ('RIGHTPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(table)
    # Duplicate/second table blocks removed for clean single-table output.

    # Build PDF with custom footer for consistent theme
    doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
    buffer.seek(0)
    return buffer

def build_monthly_attendance_grid(db, month: int, year: int, department: str = None):
    start_day, total_days = monthrange(year, month)

    # Header days (1–31)
    days = []
    for d in range(1, total_days + 1):
        day_date = date(year, month, d)
        days.append({
            "day": d,
            "weekday": day_date.strftime("%a")[:2]
        })

    user_query = db.query(User).filter(User.is_active == True)
    if department:
        user_query = user_query.filter(User.department == department)

    users = user_query.all()

    rows = []
    for user in users:
        attendance_map = {}

        records = (
            db.query(Attendance)
            .filter(
                Attendance.user_id == user.user_id,
                Attendance.check_in.between(
                    date(year, month, 1),
                    date(year, month, total_days)
                )
            )
            .all()
        )

        record_by_day = {
            r.check_in.day: r for r in records if r.check_in
        }

        for d in range(1, total_days + 1):
            day_date = date(year, month, d)

            if day_date.weekday() == 6:
                attendance_map[str(d)] = "WO"
            elif d in record_by_day:
                attendance_map[str(d)] = "P"
            else:
                attendance_map[str(d)] = "A"

        rows.append({
            "employee_id": user.employee_id,
            "name": user.name,
            "attendance": attendance_map
        })

    return {
        "title": "Daily Attendance Log",
        "duration": f"01/{month:02d}/{year} - {total_days}/{month:02d}/{year}",
        "printed_on": date.today().strftime("%d/%m/%Y"),
        "days": days,
        "rows": rows
    }
def export_monthly_grid_csv(
    db,
    month: int,
    year: int,
    department: str | None = None
):
    """
    Export Monthly Attendance Grid to CSV
    (Excel-style layout exactly like image)
    """

    data = build_monthly_attendance_grid(db, month, year, department)

    output = io.StringIO()
    writer = csv.writer(output)

    # ===============================
    # Title & Meta Rows
    # ===============================
    writer.writerow([data["title"]])
    writer.writerow([
        "Duration", data["duration"],
        "", "", "Printed", data["printed_on"]
    ])
    writer.writerow([])

    # ===============================
    # Header Rows
    # ===============================
    header_days = ["No.", "Name"]
    header_weekdays = ["", ""]

    for day in data["days"]:
        header_days.append(day["day"])
        header_weekdays.append(day["weekday"])

    writer.writerow(header_days)
    writer.writerow(header_weekdays)

    # ===============================
    # Data Rows
    # ===============================
    for index, row in enumerate(data["rows"], start=1):
        record = [index, row["name"]]
        for day in data["days"]:
            record.append(
                row["attendance"].get(str(day["day"]), "")
            )
        writer.writerow(record)

    output.seek(0)
    return output
def export_monthly_grid_pdf(
    db,
    month: int,
    year: int,
    department: str | None = None
):
    """
    Export Monthly Attendance Grid to PDF
    (Excel-like layout, landscape)
    """

    data = build_monthly_attendance_grid(db, month, year, department)

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=20,
        rightMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()
    elements = []

    # ===============================
    # Title
    # ===============================
    elements.append(
        Paragraph(f"<b>{data['title']}</b>", styles["Title"])
    )

    # ===============================
    # Meta Information
    # ===============================
    elements.append(
        Paragraph(
            f"Duration: {data['duration']} &nbsp;&nbsp;&nbsp; "
            f"Printed: {data['printed_on']}",
            styles["Normal"]
        )
    )

    # ===============================
    # Table Data
    # ===============================
    table_data = []

    header_days = ["No.", "Name"]
    header_weekdays = ["", ""]

    for day in data["days"]:
        header_days.append(str(day["day"]))
        header_weekdays.append(day["weekday"])

    table_data.append(header_days)
    table_data.append(header_weekdays)

    for index, row in enumerate(data["rows"], start=1):
        record = [str(index), row["name"]]
        for day in data["days"]:
            record.append(
                row["attendance"].get(str(day["day"]), "")
            )
        table_data.append(record)

    # ===============================
    # Column Widths
    # ===============================
    total_columns = len(header_days)
    page_width = A4[1]  # landscape width

    col_widths = (
        [35, 120] +
        [(page_width - 200) / (total_columns - 2)]
        * (total_columns - 2)
    )

    table = Table(
        table_data,
        colWidths=col_widths,
        repeatRows=2
    )

    # ===============================
    # Styling (Excel-like)
    # ===============================
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),

        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("BACKGROUND", (0, 1), (-1, 1), colors.whitesmoke),

        ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),

        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("ROWBACKGROUNDS", (0, 2), (-1, -1),
         [colors.white, colors.HexColor("#f0fdf4")]),
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return buffer

