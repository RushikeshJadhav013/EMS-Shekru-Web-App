from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.db.models.user import User
from app.enums import RoleEnum
from passlib.context import CryptContext
from app.schemas.user_schema import UserCreate, AdminCreate, AdminUpdate
from app.crud.subscription_crud import check_admin_subscription_limit
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from datetime import datetime
from typing import Optional
import io
import csv
import os
try:
    from app.config.company_config import (
        COMPANY_NAME, COMPANY_ADDRESS, COMPANY_PHONE, COMPANY_EMAIL, COMPANY_WEBSITE,
        WATERMARK_TEXT, WATERMARK_OPACITY, PRIMARY_COLOR, SECONDARY_COLOR,
        TEXT_COLOR, LIGHT_BG_COLOR, GRAY_COLOR, LOGO_PATH, USE_LOGO,
        LOGO_WIDTH, LOGO_HEIGHT, REPORT_TITLE, SHOW_EMOJIS
    )
except ImportError:
    # Default values if config file doesn't exist
    COMPANY_NAME = "YOUR COMPANY NAME"
    COMPANY_ADDRESS = "Address Line 1, City, State - PIN Code"
    COMPANY_PHONE = "+91-XXXXXXXXXX"
    COMPANY_EMAIL = "info@company.com"
    COMPANY_WEBSITE = "www.company.com"
    WATERMARK_TEXT = "YOUR COMPANY"
    WATERMARK_OPACITY = 0.1
    PRIMARY_COLOR = "#1e40af"
    SECONDARY_COLOR = "#3b82f6"
    TEXT_COLOR = "#0f172a"
    LIGHT_BG_COLOR = "#eff6ff"
    GRAY_COLOR = "#64748b"
    LOGO_PATH = None
    USE_LOGO = False
    LOGO_WIDTH = 1.5
    LOGO_HEIGHT = 0.75
    REPORT_TITLE = "EMPLOYEE DIRECTORY REPORT"
    SHOW_EMOJIS = True


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")[:72]
    return pwd_context.hash(password_bytes)

def get_user_by_email(db: Session, email: str):
    if not email:
        return None
    normalized_email = email.strip().lower()
    return (
        db.query(User)
        .filter(func.lower(User.email) == normalized_email)
        .first()
    )

def get_user_by_employee_id(db: Session, employee_id: str):
    if not employee_id:
        return None
    normalized_emp_id = employee_id.strip().lower()
    return (
        db.query(User)
        .filter(func.lower(User.employee_id) == normalized_emp_id)
        .first()
    )

def get_user_by_phone(db: Session, phone: str):
    if not phone:
        return None
    normalized_phone = phone.strip()
    return (
        db.query(User)
        .filter(User.phone == normalized_phone)
        .first()
    )

def get_user_by_pan_card(db: Session, pan_card: str):
    if not pan_card:
        return None
    normalized_pan = pan_card.strip().upper()
    return (
        db.query(User)
        .filter(User.pan_card == normalized_pan)
        .first()
    )

def get_user_by_aadhar_card(db: Session, aadhar_card: str):
    if not aadhar_card:
        return None
    normalized_aadhar = aadhar_card.strip()
    return (
        db.query(User)
        .filter(User.aadhar_card == normalized_aadhar)
        .first()
    )

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.user_id == user_id).first()

def create_user(db: Session, user: UserCreate, created_by: int = None):
    # Check subscription limit if user is being created by an admin
    if created_by is not None:
        creator = db.query(User).filter(User.user_id == created_by).first()
        if creator and creator.role == RoleEnum.ADMIN:
            can_create, current_count, max_allowed = check_admin_subscription_limit(db, created_by)
            if not can_create:
                raise ValueError(
                    f"Subscription limit reached. You have created {current_count} out of {max_allowed} allowed users. "
                    "Please upgrade your subscription plan to add more users."
                )
    
    db_user = User(
        user_id=None,
        employee_id=user.employee_id,
        name=user.name,
        gender=user.gender,
        email=user.email,
        password_hash=None,
        role=user.role,
        department=user.department,
        designation=user.designation,
        resignation_date=user.resignation_date,
        phone=user.phone,
        address=user.address,
        pan_card=user.pan_card,
        aadhar_card=user.aadhar_card,
        shift_type=user.shift_type,
        employee_type=user.employee_type,  # ✅ Added employee_type
        profile_photo=user.profile_photo
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def list_users(db: Session):
    return db.query(User).all()

def get_employees(db: Session, search: str = None, department: str = None, role: RoleEnum = None):
    query = db.query(User)
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.department.ilike(f"%{search}%")
            )
        )
    if department:
        query = query.filter(User.department == department)
    if role:
        query = query.filter(User.role == role)
    return query.all()

def update_user_role(db: Session, user_id: int, role: RoleEnum, updated_by: int = None):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user:
        user.role = role
        db.commit()
        db.refresh(user)
    return user

def update_user_status(db: Session, user_id: int, is_active: bool, updated_by: int = None):
    """Update user active/inactive status"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if user:
        user.is_active = is_active
        db.commit()
        db.refresh(user)
    return user

def delete_user(db: Session, user_id: int):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
    return user


def create_admin_user(db: Session, admin: AdminCreate, created_by: int = None):
    admin_data = admin.model_dump()
    admin_data["role"] = RoleEnum.ADMIN
    admin_data["password_hash"] = None
    # Remove created_by if it exists in admin_data (it shouldn't be in AdminCreate schema)
    admin_data.pop("created_by", None)
    db_admin = User(**admin_data)
    db.add(db_admin)
    db.commit()
    db.refresh(db_admin)
    return db_admin


def list_admin_users(db: Session):
    return db.query(User).filter(User.role == RoleEnum.ADMIN).all()


def get_admin_user(db: Session, admin_id: int):
    return (
        db.query(User)
        .filter(User.user_id == admin_id)
        .filter(User.role == RoleEnum.ADMIN)
        .first()
    )


def update_admin_user(db: Session, admin_id: int, admin_update: AdminUpdate, updated_by: int = None):
    admin = get_admin_user(db, admin_id)
    if not admin:
        return None

    for key, value in admin_update.model_dump(exclude_unset=True).items():
        if key == "role":
            continue
        setattr(admin, key, value)

    # Enforce role integrity
    admin.role = RoleEnum.ADMIN
    db.commit()
    db.refresh(admin)
    return admin


def set_admin_status(db: Session, admin_id: int, is_active: bool, updated_by: int = None):
    admin = get_admin_user(db, admin_id)
    if not admin:
        return None
    admin.is_active = is_active
    db.commit()
    db.refresh(admin)
    return admin


def delete_admin_user(db: Session, admin_id: int):
    admin = get_admin_user(db, admin_id)
    if not admin:
        return None
    db.delete(admin)
    db.commit()
    return admin


def get_admin_counts(db: Session):
    """Get counts of total, active, and inactive admin users"""
    total_admins = db.query(User).filter(User.role == RoleEnum.ADMIN).count()
    active_admins = db.query(User).filter(
        User.role == RoleEnum.ADMIN,
        User.is_active == True
    ).count()
    inactive_admins = total_admins - active_admins
    
    return {
        "total": total_admins,
        "active": active_admins,
        "inactive": inactive_admins
    }


def get_users_by_role_created_by_admin(db: Session):
    """Get counts of users by role (Note: created_by column doesn't exist, so returns all users by role)"""
    # Initialize result dictionary
    result = {}
    
    # Process each role
    for role in RoleEnum:
        # Get all users of this role (since created_by column doesn't exist in User model)
        role_users = db.query(User).filter(User.role == role).all()
        
        total = len(role_users)
        active = sum(1 for u in role_users if u.is_active and u.resignation_date is None)
        inactive = sum(1 for u in role_users if not u.is_active and u.resignation_date is None)
        resigned = sum(1 for u in role_users if u.resignation_date is not None)
        
        result[role.value] = {
            "total": total,
            "active": active,
            "inactive": inactive,
            "resigned": resigned
        }
    
    return result

def export_users_pdf(
    db: Session,
    department: Optional[str] = None,
    role: Optional[str] = None,
    designation: Optional[str] = None,
    status: Optional[bool] = None
):
    """Generate a professional PDF matching Task Management report format with optional filters"""
    buffer = io.BytesIO()
    
    # Footer drawing function - matches Task Management report exactly
    def draw_footer(canvas_obj, doc_obj):
        """Draw footer with company info and page number - two-line structure"""
        canvas_obj.saveState()
        
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
        page_text = f"Page {canvas_obj.getPageNumber()}"
        
        # Set footer text style
        canvas_obj.setFont("Helvetica", footer_font_size)
        canvas_obj.setFillColor(colors.HexColor('#64748b'))
        
        # Calculate page number width for proper spacing
        canvas_obj.setFont("Helvetica-Bold", footer_font_size)
        page_num_width = canvas_obj.stringWidth(page_text, "Helvetica-Bold", footer_font_size)
        canvas_obj.setFont("Helvetica", footer_font_size)
        
        # Calculate available width for first line (full width minus padding)
        available_width_line1 = A4[0] - (horizontal_padding * 2)
        
        # Calculate available width for second line (minus page number space)
        spacing_between_copyright_and_page = 15  # Space between copyright and page number
        available_width_line2 = A4[0] - (horizontal_padding * 2) - page_num_width - spacing_between_copyright_and_page
        
        # Wrap first line if needed (intelligent wrapping at separator points)
        first_line_final = first_line_text
        if canvas_obj.stringWidth(first_line_text, "Helvetica", footer_font_size) > available_width_line1:
            # Split first line intelligently
            parts = first_line_text.split(' | ')
            wrapped_lines = []
            current_line = ""
            for part in parts:
                separator = " | " if current_line else ""
                test_line = current_line + separator + part
                if canvas_obj.stringWidth(test_line, "Helvetica", footer_font_size) <= available_width_line1:
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
        if canvas_obj.stringWidth(copyright_text, "Helvetica", footer_font_size) > available_width_line2:
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
        canvas_obj.setStrokeColor(colors.HexColor('#1e40af'))
        canvas_obj.setLineWidth(footer_line_thickness)
        canvas_obj.line(horizontal_padding, footer_line_y, A4[0] - horizontal_padding, footer_line_y)
        
        # Draw first line (Address | Website | Email | Contact)
        canvas_obj.setFont("Helvetica", footer_font_size)
        canvas_obj.setFillColor(colors.HexColor('#64748b'))
        canvas_obj.drawString(horizontal_padding, footer_text_top, first_line_final)
        
        # Draw second line: Copyright (left) + Page number (right)
        # Draw copyright text
        canvas_obj.drawString(horizontal_padding, footer_text_bottom, copyright_final)
        
        # Draw page number (right-aligned)
        canvas_obj.setFont("Helvetica-Bold", footer_font_size)
        canvas_obj.setFillColor(colors.HexColor('#1e40af'))
        page_x = A4[0] - horizontal_padding
        canvas_obj.drawRightString(page_x, footer_text_bottom, page_text)
        
        canvas_obj.restoreState()
    
    # Create document - matching Task Management report margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=36,
        bottomMargin=80  # Increased bottom margin for footer spacing
    )
    
    # Custom styles
    styles = getSampleStyleSheet()
    
    # Title style - matching Task Management report
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.black,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=12
    )
    
    elements = []
    
    # Title - matching Task Management report
    elements.append(Paragraph("Employee Directory Report", title_style))
    elements.append(Spacer(1, 12))
    
    # Fetch all users
    users = db.query(User).all()
    
    # Info block - matching Task Management report format
    info_data = [
        ['Company Name', COMPANY_NAME or ''],
        ['Total Employees', str(len(users))],
        ['Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        ['Report Type', 'Employee Directory'],
    ]
    
    info_table = Table(info_data, colWidths=[1.5*inch, 5*inch])
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
    
    # Table headers
    headers = [
        'Employee ID', 'Name', 'Role', 'Department', 'Designation', 
        'Email', 'Phone', 'Shift'
    ]
    
    # Build table data
    table_data = []
    for user in users:
        table_data.append([
            user.employee_id or "",
            user.name or "",
            user.role.value if hasattr(user.role, 'value') else str(user.role),
            user.department or "",
            user.designation or "",
            user.email or "",
            user.phone or "",
            user.shift_type or ""
        ])
    
    # Calculate column widths
    num_cols = len(headers)
    total_width = A4[0] - 60  # Total width minus margins
    col_widths = [total_width / num_cols] * num_cols
    
    # Cell styles for text wrapping
    body_cell_style = ParagraphStyle(
        'body_cell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.black,
        alignment=TA_LEFT,
        leading=11,
        wordWrap='CJK',
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
    
    # Build table with wrapped text
    table_rows = [[Paragraph(h, header_cell_style) for h in headers]]
    for row in table_data:
        table_rows.append([Paragraph(str(cell) if cell else '', body_cell_style) for cell in row])
    
    table = Table(table_rows, repeatRows=1, colWidths=col_widths)
    
    # Table styling - matching Task Management report exactly
    table.setStyle(TableStyle([
        # Header styling - matching Task Management report
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Table body styling
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        
        # Grid - matching Task Management report
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e6edf3')),
    ]))
    
    elements.append(table)
    
    # Build PDF with footer
    doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
    buffer.seek(0)
    return buffer

def export_users_csv(db: Session):
    output = io.StringIO()
    writer = csv.writer(output)

    # Fetch all users
    users = db.query(User).all()

    # CSV Header
    writer.writerow(["Employee ID", "Name", "Email", "Role", "Department", "Designation", "Phone", "Address", "PAN Card", "Aadhaar Card", "Shift Type", "Joining Date", "Status"])

    # CSV Data
    for user in users:
        writer.writerow([
            user.employee_id,
            user.name,
            user.email,
            user.role.value,
            user.department or "",
            user.designation or "",
            user.phone or "",
            user.address or "",
            user.pan_card or "",
            user.aadhar_card or "",
            user.shift_type or "",
            user.joining_date.strftime("%Y-%m-%d") if user.joining_date else "",
            "Active" if user.is_active else "Inactive"
        ])

    output.seek(0)
    return output
