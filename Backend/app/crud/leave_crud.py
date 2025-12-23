from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional, List
import io
import csv

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from app.db.models.leave import Leave
from app.db.models.user import User
from app.config.company_config import (
    COMPANY_NAME, COMPANY_ADDRESS, COMPANY_PHONE, COMPANY_EMAIL, COMPANY_WEBSITE
)


def export_leave_csv(
    db: Session,
    start_date: datetime = None,
    end_date: datetime = None,
    department: Optional[str] = None,
):
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['Leave Report'])
    writer.writerow([f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
    writer.writerow([])

    # Columns
    headers = ['Leave ID', 'Employee ID', 'Name', 'Department', 'Leave Type', 'Start Date', 'End Date', 'Total Days', 'Status', 'Reason']
    writer.writerow(headers)

    query = db.query(Leave, User.employee_id, User.name, User.department).join(User, Leave.user_id == User.user_id)
    if department:
        query = query.filter(func.lower(User.department) == department.strip().lower())
    if start_date:
        query = query.filter(Leave.start_date >= start_date)
    if end_date:
        query = query.filter(Leave.end_date <= end_date)

    for leave, emp_id, name, dept in query.order_by(Leave.start_date.desc()).all():
        total_days = (leave.end_date - leave.start_date).days + 1 if leave.start_date and leave.end_date else ""
        writer.writerow([
            leave.leave_id,
            emp_id or leave.user_id,
            name or "",
            dept or "",
            leave.leave_type or "",
            leave.start_date.strftime("%Y-%m-%d") if leave.start_date else "",
            leave.end_date.strftime("%Y-%m-%d") if leave.end_date else "",
            total_days,
            leave.status or "",
            (leave.reason or "").replace("\n", " ").strip()
        ])

    output.seek(0)
    return output


def export_leave_pdf(
    db: Session,
    start_date: datetime = None,
    end_date: datetime = None,
    department: Optional[str] = None,
):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=50, bottomMargin=80)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    elements.append(Paragraph("Leave Report", title_style))
    elements.append(Spacer(1, 12))

    # Info table
    info_data = [
        ['Company Name:', COMPANY_NAME],
        ['Department:', department or 'All Departments'],
        ['Period:', f"{start_date.strftime('%Y-%m-%d') if start_date else 'Any'} to {end_date.strftime('%Y-%m-%d') if end_date else 'Any'}"],
        ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
    ]
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eff6ff')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.black),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 16))

    # Data query
    query = db.query(Leave, User.employee_id, User.name, User.department).join(User, Leave.user_id == User.user_id)
    if department:
        query = query.filter(func.lower(User.department) == department.strip().lower())
    if start_date:
        query = query.filter(Leave.start_date >= start_date)
    if end_date:
        query = query.filter(Leave.end_date <= end_date)

    rows = []
    for leave, emp_id, name, dept in query.order_by(Leave.start_date.desc()).all():
        total_days = (leave.end_date - leave.start_date).days + 1 if leave.start_date and leave.end_date else ""
        rows.append([
            str(leave.leave_id),
            emp_id or str(leave.user_id),
            name or "",
            dept or "",
            leave.leave_type or "",
            leave.start_date.strftime("%Y-%m-%d") if leave.start_date else "",
            leave.end_date.strftime("%Y-%m-%d") if leave.end_date else "",
            str(total_days),
            leave.status or "",
            (leave.reason or "").strip()
        ])

    # Columns and conditional visibility
    headers = ['Leave ID', 'Employee ID', 'Name', 'Department', 'Leave Type', 'Start Date', 'End Date', 'Total Days', 'Status', 'Reason']
    data = [headers] + rows

    # Determine visible columns
    num_cols = len(headers)
    columns_with_data = [False] * num_cols
    essential = {0, 1, 2}
    for i in essential:
        columns_with_data[i] = True
    for r in rows:
        for idx, cell in enumerate(r):
            text = "" if cell is None else str(cell).strip()
            if text and text.lower() not in ("n/a", "na", "-"):
                columns_with_data[idx] = True

    visible_cols = [i for i, v in enumerate(columns_with_data) if v]
    visible_count = len(visible_cols) if visible_cols else num_cols
    total_width = A4[0] - (doc.leftMargin + doc.rightMargin)
    base_fractions = [0.07, 0.10, 0.18, 0.10, 0.10, 0.10, 0.10, 0.08, 0.07, 0.10]
    if len(base_fractions) != num_cols:
        base_fractions = [1.0 / num_cols] * num_cols
    visible_fractions = [base_fractions[i] for i in visible_cols]
    frac_sum = sum(visible_fractions) if visible_fractions else 1.0
    normalized = [f / frac_sum for f in visible_fractions]
    col_widths = [total_width * f for f in normalized]

    # Build table rows using visible columns
    styles_tbl = getSampleStyleSheet()
    header_style = ParagraphStyle('Header', parent=styles_tbl['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.whitesmoke, alignment=TA_CENTER)
    cell_style = ParagraphStyle('Cell', parent=styles_tbl['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.black, alignment=TA_LEFT)
    cell_center = ParagraphStyle('CellCenter', parent=cell_style, alignment=TA_CENTER)

    table_rows = []
    table_rows.append([Paragraph(headers[i], header_style) for i in visible_cols])
    for r in rows:
        row_cells = []
        for idx in visible_cols:
            text = "" if r[idx] is None else str(r[idx])
            if idx in (0, 1, 5, 6, 7):
                row_cells.append(Paragraph(text, cell_center))
            else:
                row_cells.append(Paragraph(text, cell_style))
        table_rows.append(row_cells)

    table = Table(table_rows, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 1), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 1), (-1, -1), 6),
        ('RIGHTPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))

    elements.append(table)

    # Footer function copied for consistency
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
        available_width_line1 = A4[0] - (horizontal_padding * 2)
        spacing_between_copyright_and_page = 15
        available_width_line2 = A4[0] - (horizontal_padding * 2) - page_num_width - spacing_between_copyright_and_page

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
        canvas.line(horizontal_padding, footer_line_y, A4[0] - horizontal_padding, footer_line_y)

        canvas.setFont("Helvetica", footer_font_size)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(horizontal_padding, footer_text_top, first_line_final)

        canvas.drawString(horizontal_padding, footer_text_bottom, copyright_final)

        canvas.setFont("Helvetica-Bold", footer_font_size)
        canvas.setFillColor(colors.HexColor('#1e40af'))
        page_x = A4[0] - horizontal_padding
        canvas.drawRightString(page_x, footer_text_bottom, page_text)
        canvas.restoreState()

    doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
    buffer.seek(0)
    return buffer

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from typing import List, Optional
from app.utils.timezone import now_ist
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

    # Get the user who is deleting the leave for notification purposes
    requester = db.query(User).filter(User.user_id == user_id).first()
    
    # Create deletion notification for approvers before deleting the leave
    if requester:
        create_leave_deletion_notification(db, leave, requester)

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
    now = now_ist()
    
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
    from sqlalchemy.orm import joinedload
    return (
        db.query(Leave)
        .options(joinedload(Leave.user))
        .join(User, User.user_id == Leave.user_id)
        .filter(Leave.status == "Pending", User.role.in_(roles))
        .all()
    )


def list_pending_by_department_and_roles(db: Session, department: str, roles: list[str]):
    from sqlalchemy.orm import joinedload
    return (
        db.query(Leave)
        .options(joinedload(Leave.user))
        .join(User, User.user_id == Leave.user_id)
        .filter(Leave.status == "Pending", User.department == department, User.role.in_(roles))
        .all()
    )


def list_decided_by_approver(db: Session, approver_id: int):
    # Fallback implementation without approver tracking fields.
    # Returns all leaves that have been decided (not Pending) with user details.
    from sqlalchemy.orm import joinedload
    return (
        db.query(Leave)
        .options(joinedload(Leave.user))
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


def create_leave_deletion_notification(db: Session, leave: Leave, requester: User) -> List[LeaveNotification]:
    """
    Create notifications for approvers when a leave request is withdrawn/deleted by the requester.
    These notifications will persist after the leave is deleted by using a NULL leave_id.
    """
    recipients = _get_leave_notification_recipients(db, requester)
    if not recipients:
        return []

    # Format dates
    start_str = leave.start_date.strftime("%d %b %Y")
    end_str = leave.end_date.strftime("%d %b %Y")
    day_count = (leave.end_date.date() - leave.start_date.date()).days + 1
    day_label = "day" if day_count == 1 else "days"

    title = "Leave Request Withdrawn"
    message = (
        f"{requester.name} ({requester.employee_id or 'N/A'}) from {requester.department or 'N/A'} department "
        f"has withdrawn their leave request for {start_str} to {end_str} ({day_count} {day_label})."
    )

    notifications: List[LeaveNotification] = []
    for recipient in recipients:
        # Create a standalone notification that doesn't reference the leave (to avoid CASCADE deletion)
        notification = LeaveNotification(
            user_id=recipient.user_id,
            leave_id=None,  # Set to None so it won't be deleted when leave is removed
            notification_type="Leave Withdrawal",
            title=title,
            message=message,
            is_read=False,
        )
        db.add(notification)
        notifications.append(notification)

    # Commit the notifications before the leave is deleted
    db.commit()
    for notification in notifications:
        db.refresh(notification)

    return notifications


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
