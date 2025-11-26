from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.db.models.user import User
from app.enums import RoleEnum
from passlib.context import CryptContext
from app.schemas.user_schema import UserCreate
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from datetime import datetime
import io
import csv
import os
try:
    from app.config.company_config import (
        COMPANY_NAME, COMPANY_ADDRESS, COMPANY_PHONE, COMPANY_EMAIL,
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

def create_user(db: Session, user: UserCreate):
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

def update_user_role(db: Session, user_id: int, role: RoleEnum):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user:
        user.role = role
        db.commit()
        db.refresh(user)
    return user

def update_user_status(db: Session, user_id: int, is_active: bool):
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

def export_users_pdf(db: Session):
    """Generate a modern, professional PDF with company branding and hierarchical organization"""
    buffer = io.BytesIO()
    
    # Custom page template with watermark
    class WatermarkedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            canvas.Canvas.__init__(self, *args, **kwargs)
            
        def showPage(self):
            self.saveState()
            # Add watermark (company logo/name with transparency)
            self.setFillColorRGB(0.9, 0.9, 0.9, alpha=WATERMARK_OPACITY)
            self.setFont("Helvetica-Bold", 60)
            self.saveState()
            self.translate(A4[0]/2, A4[1]/2)
            self.rotate(45)
            self.drawCentredString(0, 0, WATERMARK_TEXT)
            self.restoreState()
            
            # Add footer with page number
            self.setFillColorRGB(0.4, 0.4, 0.4)
            self.setFont("Helvetica", 8)
            page_num = f"Page {self.getPageNumber()}"
            self.drawRightString(A4[0] - 0.5*inch, 0.5*inch, page_num)
            self.drawString(0.5*inch, 0.5*inch, f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
            
            self.restoreState()
            canvas.Canvas.showPage(self)
    
    # Create document with custom canvas
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Custom styles
    styles = getSampleStyleSheet()

    # Company header style
    company_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor(PRIMARY_COLOR),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Subtitle style
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor(GRAY_COLOR),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )
    
    # Department header style
    dept_style = ParagraphStyle(
        'DepartmentHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor(TEXT_COLOR),
        spaceBefore=20,
        spaceAfter=10,
        fontName='Helvetica-Bold',
        borderColor=colors.HexColor(SECONDARY_COLOR),
        borderWidth=0,
        borderPadding=5,
        backColor=colors.HexColor(LIGHT_BG_COLOR)
    )
    
    # Role hierarchy mapping
    role_hierarchy = {
        'ADMIN': 1,
        'HR': 2,
        'MANAGER': 3,
        'TEAM_LEAD': 4,
        'EMPLOYEE': 5
    }
    
    elements = []
    
    # Add company logo if available
    if USE_LOGO and LOGO_PATH and os.path.exists(LOGO_PATH):
        try:
            logo = Image(LOGO_PATH, width=LOGO_WIDTH*inch, height=LOGO_HEIGHT*inch)
            logo.hAlign = 'CENTER'
            elements.append(logo)
            elements.append(Spacer(1, 0.1*inch))
        except:
            pass  # Skip logo if there's an error
    
    # Company Header
    elements.append(Paragraph(COMPANY_NAME, company_style))
    elements.append(Paragraph(
        f"{COMPANY_ADDRESS} | Phone: {COMPANY_PHONE} | Email: {COMPANY_EMAIL}",
        subtitle_style
    ))
    elements.append(Spacer(1, 0.1*inch))
    
    # Report Title
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor(TEXT_COLOR),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    elements.append(Paragraph(REPORT_TITLE, title_style))
    
    # Report metadata
    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor(GRAY_COLOR),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    # Fetch all users
    users = db.query(User).all()
    elements.append(Paragraph(
        f"Total Employees: {len(users)} | Report Generated: {datetime.now().strftime('%B %d, %Y')}",
        meta_style
    ))
    elements.append(Spacer(1, 0.2*inch))
    
    # Group users by department and sort by role hierarchy
    departments = {}
    for user in users:
        dept = user.department or "Unassigned"
        if dept not in departments:
            departments[dept] = []
        departments[dept].append(user)
    
    # Sort departments alphabetically
    for dept in sorted(departments.keys()):
        # Sort employees within department by role hierarchy, then by name
        dept_users = sorted(
            departments[dept],
            key=lambda u: (role_hierarchy.get(u.role.value, 999), u.name)
        )
        
        # Department header
        elements.append(Paragraph(f"📁 {dept.upper()}", dept_style))
        elements.append(Spacer(1, 0.1*inch))
        
        # Create table for this department
        table_data = [[
            "ID", "Name", "Role", "Designation", "Email", "Phone", "Shift"
        ]]
        
        for user in dept_users:
            # Add role emoji for visual hierarchy
            if SHOW_EMOJIS:
                role_emoji = {
                    'ADMIN': '👑 ',
                    'HR': '👥 ',
                    'MANAGER': '📊 ',
                    'TEAM_LEAD': '🎯 ',
                    'EMPLOYEE': '👤 '
                }.get(user.role.value, '👤 ')
            else:
                role_emoji = ''
            
            table_data.append([
                user.employee_id or "",
                user.name[:20] if user.name else "",  # Truncate long names
                f"{role_emoji}{user.role.value}",
                user.designation[:15] if user.designation else "",
                user.email[:25] if user.email else "",
                user.phone[:15] if user.phone else "",
                user.shift_type or ""
            ])
        
        # Modern table styling
        col_widths = [0.8*inch, 1.5*inch, 1.2*inch, 1.2*inch, 1.8*inch, 1.0*inch, 0.7*inch]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        table.setStyle(TableStyle([
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(PRIMARY_COLOR)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Data rows styling
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # ID column centered
            ('ALIGN', (1, 1), (-1, -1), 'LEFT'),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            
            # Alternating row colors for better readability
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
            
            # Vertical alignment
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))
    
    # Build PDF with custom canvas
    doc.build(elements, canvasmaker=WatermarkedCanvas)
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
