"""
Salary PDF Service - Generate Salary Slip, Increment Letter, and Salary Annexure PDFs
Matches the exact format from provided samples using ReportLab
"""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfgen import canvas
from typing import Optional
import os

# Company configuration
try:
    from app.config.company_config import (
        COMPANY_NAME, COMPANY_ADDRESS, COMPANY_PHONE, COMPANY_EMAIL, COMPANY_WEBSITE,
        LOGO_PATH, USE_LOGO, LOGO_WIDTH, LOGO_HEIGHT
    )
except ImportError:
    COMPANY_NAME = "Shekru Labs India Pvt Ltd"
    COMPANY_ADDRESS = "Office 2nd Floor, Manogat Appt., Treasure Park Road, Sahakar Nagar, Pune, Maharashtra 411009"
    COMPANY_PHONE = "+91-XXXXXXXXXX"
    COMPANY_EMAIL = "info@shekrulabs.com"
    COMPANY_WEBSITE = "www.shekrulabs.com"
    LOGO_PATH = "assets/logo.png"
    USE_LOGO = False
    LOGO_WIDTH = 2.5
    LOGO_HEIGHT = 2.0

# Colors matching the sample
HEADER_GREEN = colors.HexColor('#4CAF50')  # Green header bar
HEADER_ORANGE = colors.HexColor('#FF9800')  # Orange accent
GRAY_BG = colors.HexColor('#E0E0E0')  # Gray background for section headers
LIGHT_GRAY = colors.HexColor('#F5F5F5')
WHITE = colors.white
BLACK = colors.black


def format_currency(amount: float) -> str:
    """Format amount as Indian currency"""
    if amount == 0:
        return "-"
    return f"{amount:,.2f}"


def format_currency_int(amount: float) -> str:
    """Format amount as Indian currency without decimals"""
    if amount == 0:
        return "-"
    return f"{int(amount):,}"


def get_month_name(month: int) -> str:
    """Get month name from number"""
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    return months[month - 1] if 1 <= month <= 12 else ""


def ordinal(n: int) -> str:
    """Convert number to ordinal (1st, 2nd, 3rd, etc.)"""
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


def generate_salary_slip_pdf(
    employee_name: str,
    employee_id: str,
    designation: str,
    location: str,
    doj: str,
    pan: str,
    uan: str,
    month: int,
    year: int,
    working_days: int,
    pf: str,
    variable_pay: float,
    # Earnings
    basic: float,
    hra: float,
    special_allowance: float,
    medical_allowance: float,
    conveyance: float,
    other_allowance: float,
    # Deductions
    professional_tax: float,
    other_deduction: float,
    payment_mode: str = "Bank Transfer"
) -> io.BytesIO:
    """
    Generate Salary Slip PDF matching the exact sample format
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Calculate totals
    total_earnings = basic + hra + special_allowance + medical_allowance + conveyance + other_allowance
    total_deductions = professional_tax + other_deduction
    net_payable = total_earnings - total_deductions
    
    # Page width for calculations
    page_width = A4[0] - 60  # minus margins
    
    # ===== HEADER SECTION =====
    # Company Logo (or fallback to name) centered
    header_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#4CAF50'),  # Green
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=5
    )
    
    if USE_LOGO and LOGO_PATH and os.path.exists(LOGO_PATH):
        # Render logo image instead of text header
        logo = Image(LOGO_PATH, width=LOGO_WIDTH * inch, height=LOGO_HEIGHT * inch)
        logo.hAlign = 'CENTER'
        elements.append(logo)
    else:
        # Fallback to text header if logo not available
        elements.append(Paragraph(COMPANY_NAME, header_style))
    
    # Registered Office Address (stacked on multiple lines like sample)
    address_style = ParagraphStyle(
        'Address',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=BLACK,
        spaceAfter=15
    )
    address_parts = COMPANY_ADDRESS.split(", ")
    if len(address_parts) >= 6:
        line_one = ", ".join(address_parts[:3]) + ","
        line_two = ", ".join(address_parts[3:])
        address_html = f"Registered Office:<br/>{line_one}<br/>{line_two}"
    else:
        address_html = f"Registered Office:<br/>{COMPANY_ADDRESS}"
    elements.append(Paragraph(address_html, address_style))
    
    # Set the col_widths for earnings/deductions and use for both tables
    col_widths = [1.6*inch, 1.5*inch, 1.6*inch, 1.5*inch]
    # ===== PAYSLIP HEADER BAR =====
    month_name = get_month_name(month)
    payslip_header = [[f"Payslip For the Month of {month_name}- {year}"]]
    payslip_header_table = Table(payslip_header, colWidths=[sum(col_widths)])
    payslip_header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GRAY_BG),
        ('TEXTCOLOR', (0, 0), (-1, -1), BLACK),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 1, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(payslip_header_table)
    
    # ===== EMPLOYEE NAME ROW =====
    emp_name_data = [["Employee Name", ":", employee_name]]
    # Use column widths proportional to the earnings table's total width
    emp_name_total_width = sum(col_widths)
    emp_name_col_widths = [emp_name_total_width * 0.18, emp_name_total_width * 0.04, emp_name_total_width * 0.78]
    emp_name_table = Table(emp_name_data, colWidths=emp_name_col_widths)
    emp_name_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),  # Bold colon to match label/value
        ('FONTNAME', (2, 0), (2, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
    ]))
    elements.append(emp_name_table)
    
    # ===== EMPLOYEE DETAILS SECTION =====
    col_width = page_width / 2
    details_data = [
        [
            Table([["Employee Id", ":", employee_id]], colWidths=[1.2*inch, 0.2*inch, col_width - 1.6*inch]),
            Table([["Location", ":", location]], colWidths=[1.2*inch, 0.2*inch, col_width - 1.6*inch])
        ],
        [
            Table([["Designation", ":", designation]], colWidths=[1.2*inch, 0.2*inch, col_width - 1.6*inch]),
            Table([["Working Days", ":", str(working_days)]], colWidths=[1.2*inch, 0.2*inch, col_width - 1.6*inch])
        ],
        [
            Table([["DOJ", ":", doj]], colWidths=[1.2*inch, 0.2*inch, col_width - 1.6*inch]),
            Table([["PF", ":", pf]], colWidths=[1.2*inch, 0.2*inch, col_width - 1.6*inch])
        ],
        [
            Table([["PAN", ":", pan]], colWidths=[1.2*inch, 0.2*inch, col_width - 1.6*inch]),
            Table([["Variable Pay*", ":", format_currency(variable_pay)]], colWidths=[1.2*inch, 0.2*inch, col_width - 1.6*inch])
        ],
        [
            Table([["UAN", ":", uan]], colWidths=[1.2*inch, 0.2*inch, col_width - 1.6*inch]),
            ""
        ],
    ]
    
    # Style for inner tables
    inner_style = TableStyle([
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),  # Label bold
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),  # Colon bold to match label/value
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])
    
    for row in details_data:
        for cell in row:
            if isinstance(cell, Table):
                cell.setStyle(inner_style)
    
    details_total_width = sum(col_widths)
    details_table = Table(details_data, colWidths=[details_total_width / 2, details_total_width / 2])
    details_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 1, BLACK),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 10))
    
    # ===== EARNINGS AND DEDUCTIONS TABLE =====
    earnings_col_width = page_width / 2
    
    # Header row
    earnings_header = [["Earnings", "Amount(Rs)", "Deductions", "Amount(Rs)"]]
    
    # Data rows - align earnings and deductions side by side
    earnings_deductions_data = [
        ["Basic", format_currency(basic), "Professional Tax", format_currency(professional_tax)],
        ["House Rent Allowance", format_currency(hra), "Other", format_currency(other_deduction)],
        ["Special Allowance", format_currency(special_allowance), "", ""],
        ["Medical Allowance", format_currency(medical_allowance), "", ""],
        ["Conveyance Allowance", format_currency(conveyance), "", ""],
        ["Other Allowance", format_currency(other_allowance), "", ""],
    ]
    
    # Total row
    total_row = [["Total Earnings", format_currency(total_earnings), "Total Deductions", format_currency(total_deductions)]]
    
    # Combine all
    full_table_data = earnings_header + earnings_deductions_data + total_row
    
    col_widths = [1.6*inch, 1.5*inch, 1.6*inch, 1.5*inch]
    earnings_table = Table(full_table_data, colWidths=col_widths)
    earnings_table.setStyle(TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (1, 0), GRAY_BG),
        ('BACKGROUND', (2, 0), (3, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        
        # Data styling
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
        
        # Total row styling
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (1, -1), LIGHT_GRAY),
        ('BACKGROUND', (2, -1), (3, -1), LIGHT_GRAY),
        
        # Grid
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 1, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(earnings_table)
    
    # ===== PAYMENT INFO AND NET PAYABLE (left-aligned as 'Earnings') =====
    payment_col_widths = [sum(col_widths) * 0.25, sum(col_widths) * 0.05, sum(col_widths) * 0.70]
    payment_data = [
        ["Mode of Payment", ":", payment_mode],
        ["Total Net Payable", ":", format_currency(net_payable)]
    ]
    payment_table = Table(payment_data, colWidths=payment_col_widths)
    payment_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),   # Label bold
        ('FONTNAME', (1,0), (1,-1), 'Helvetica-Bold'),   # Colon bold to match label/value
        ('FONTNAME', (2,0), (2,0), 'Helvetica-Bold'),    # Payment value bold
        ('FONTNAME', (2,1), (2,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('ALIGN', (2,0), (2,-1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
    ]))
    elements.append(payment_table)

    # ===== FOOTER NOTE =====
    # Statement below the last table: "This is system generated payslip and does not require authentication."
    footer_note_style = ParagraphStyle(
        'FooterNote',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=BLACK,
        spaceBefore=8,
    )
    elements.append(Paragraph("This is system generated payslip and does not require authentication.", footer_note_style))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_salary_annexure_pdf(
    employee_name: str,
    designation: str,
    location: str,
    # Annual components
    basic_annual: float,
    hra_annual: float,
    special_allowance_annual: float,
    conveyance_annual: float,
    medical_allowance_annual: float,
    other_allowance_annual: float,
    # Deductions
    professional_tax_annual: float,
    other_deduction_annual: float,
) -> io.BytesIO:
    """
    Generate Salary Annexure PDF matching the exact sample format
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    elements = []
    styles = getSampleStyleSheet()
    page_width = A4[0] - 80  # minus margins
    
    # Calculate monthly values
    basic_monthly = round(basic_annual / 12, 2)
    hra_monthly = round(hra_annual / 12, 2)
    special_monthly = round(special_allowance_annual / 12, 2)
    conveyance_monthly = round(conveyance_annual / 12, 2)
    medical_monthly = round(medical_allowance_annual / 12, 2)
    other_monthly = round(other_allowance_annual / 12, 2)
    
    # Calculate totals
    total_ctc_annual = (basic_annual + hra_annual + special_allowance_annual + 
                        conveyance_annual + medical_allowance_annual + other_allowance_annual)
    monthly_ctc = round(total_ctc_annual / 12, 2)
    total_deductions_annual = professional_tax_annual + other_deduction_annual
    monthly_in_hand = round((total_ctc_annual - total_deductions_annual) / 12, 2)
    
    # ===== TITLE =====
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=BLACK,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=20
    )
    elements.append(Paragraph("Salary Annexure", title_style))
    elements.append(Spacer(1, 15))
    
    # ===== EMPLOYEE INFO TABLE =====
    info_data = [
        ["Company Name:", COMPANY_NAME],
        ["Candidate Name:", employee_name],
        ["Designation:", designation],
        ["Location:", location],
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, page_width - 2*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 1, BLACK),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))
    
    # ===== SALARY COMPONENTS TABLE =====
    col_widths = [2.5*inch, 1.5*inch, 1.5*inch]
    
    # Components section
    components_data = [
        ["Components", "Per Annum", "Per Month"],
        ["Basic", format_currency_int(basic_annual), format_currency(basic_monthly)],
        ["HRA", format_currency_int(hra_annual), format_currency(hra_monthly)],
        ["Special Allowance", format_currency_int(special_allowance_annual), format_currency(special_monthly)],
        ["Conveyance", format_currency_int(conveyance_annual), format_currency(conveyance_monthly)],
        ["Medical Allowance", format_currency_int(medical_allowance_annual), format_currency(medical_monthly)],
        ["Other", format_currency_int(other_allowance_annual), format_currency(other_monthly)],
    ]
    
    components_table = Table(components_data, colWidths=col_widths)
    components_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Data
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 1, BLACK),
    ]))
    elements.append(components_table)
    elements.append(Spacer(1, 10))
    
    # ===== DEDUCTIONS TABLE =====
    # Professional tax note for monthly variation
    pt_monthly_note = f"PM 200 In Feb 300" if professional_tax_annual > 0 else "-"
    
    deductions_data = [
        ["Deductions Amount(B)", "Per Annum", "Per Month"],
        ["Professional Tax Deduction", format_currency_int(professional_tax_annual), pt_monthly_note],
        ["Other", format_currency_int(other_deduction_annual), format_currency(round(other_deduction_annual / 12, 2))],
    ]
    
    deductions_table = Table(deductions_data, colWidths=col_widths)
    deductions_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Data
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 1, BLACK),
    ]))
    elements.append(deductions_table)
    elements.append(Spacer(1, 10))
    
    # ===== CTC SUMMARY TABLE =====
    ctc_data = [
        ["CTC", "Pay", "Pay"],
        ["Total Cost To Company:", format_currency_int(total_ctc_annual), "-"],
        ["Monthly CTC", "-", format_currency_int(monthly_ctc)],
        ["Monthly CTC In Hand", "-", format_currency_int(monthly_in_hand)],
    ]
    
    ctc_table = Table(ctc_data, colWidths=col_widths)
    ctc_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Data
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 1, BLACK),
    ]))
    elements.append(ctc_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_increment_letter_pdf(
    employee_name: str,
    designation: str,
    location: str,
    previous_salary: float,
    increment_amount: float,
    new_salary: float,
    effective_date: datetime,
    letter_date: Optional[datetime] = None
) -> io.BytesIO:
    """
    Generate Increment Letter PDF matching the exact sample format
    """
    buffer = io.BytesIO()
    
    # Use canvas for more control over positioning
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Margins
    left_margin = 50
    right_margin = width - 50
    top_margin = height - 50
    
    # ===== GREEN HEADER BAR =====
    c.setFillColor(HEADER_GREEN)
    c.rect(0, height - 30, width, 30, fill=True, stroke=False)
    
    # ===== COMPANY LOGO (Right side) =====
    # Draw logo text "Shekru labs" style
    logo_x = right_margin - 100
    logo_y = height - 70
    
    # Green bracket
    c.setFillColor(HEADER_GREEN)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(logo_x, logo_y, "(")
    
    # Orange "Shekru labs" text
    c.setFillColor(HEADER_ORANGE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(logo_x + 15, logo_y, "Shekru labs")
    
    # ===== DATE =====
    if letter_date is None:
        letter_date = datetime.now()
    
    date_str = letter_date.strftime("%d %B %Y")
    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, height - 100, f"Date: {date_str}")
    
    # ===== TO SECTION =====
    y_pos = height - 140
    c.setFont("Helvetica", 11)
    c.drawString(left_margin, y_pos, "To,")
    
    y_pos -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y_pos, f"Mr. {employee_name},")
    
    y_pos -= 18
    c.setFont("Helvetica", 11)
    c.drawString(left_margin, y_pos, f"{designation}, {location}.")
    
    # ===== SUBJECT =====
    y_pos -= 50
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y_pos, "Sub: Letter of Increment")
    
    # ===== GREETING =====
    y_pos -= 40
    c.setFont("Helvetica-Bold", 11)
    first_name = employee_name.split()[0] if employee_name else "Employee"
    c.drawString(left_margin, y_pos, f"Dear {first_name},")
    
    # ===== BODY TEXT =====
    y_pos -= 30
    c.setFont("Helvetica", 11)
    
    # Format effective date with ordinal
    eff_day = ordinal(effective_date.day)
    eff_month = effective_date.strftime("%B")
    eff_year = effective_date.year
    
    # First paragraph
    text_width = right_margin - left_margin
    body_text = (
        f"We are pleased to inform you that after evaluating your performance we are your monthly salary "
        f"has been revised w.e.f {eff_day} {eff_month} {eff_year}, and the new salary structure will be:"
    )
    
    # Draw wrapped text
    from reportlab.pdfbase.pdfmetrics import stringWidth
    
    words = body_text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = current_line + " " + word if current_line else word
        if stringWidth(test_line, "Helvetica", 11) < text_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    
    for line in lines:
        c.drawString(left_margin, y_pos, line)
        y_pos -= 18
    
    # ===== SALARY DETAILS =====
    y_pos -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y_pos, f"Previous Salary: {format_currency(previous_salary)}/-")
    
    y_pos -= 20
    c.drawString(left_margin, y_pos, f"Increment: {format_currency(increment_amount)}/-")
    
    y_pos -= 20
    c.drawString(left_margin, y_pos, f"New Salary: {format_currency(new_salary)}/-")
    
    # ===== CLOSING PARAGRAPH =====
    y_pos -= 40
    c.setFont("Helvetica", 11)
    
    closing_text = (
        "For remaining salary breakup details and other terms and conditions please contact the HR "
        "department. We look forward to your valuable contributions to the organization and wishing "
        "you a great career ahead. Please sign the duplicate copy of this letter as a token of acceptance of "
        "the same."
    )
    
    words = closing_text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = current_line + " " + word if current_line else word
        if stringWidth(test_line, "Helvetica", 11) < text_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    
    for line in lines:
        c.drawString(left_margin, y_pos, line)
        y_pos -= 18
    
    # ===== SIGNATURE SECTION =====
    y_pos -= 50
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y_pos, "Yours Sincerely,")
    
    y_pos -= 40
    c.drawString(left_margin, y_pos, "For " + COMPANY_NAME)
    
    y_pos -= 50
    c.drawString(left_margin, y_pos, "_______________________")
    y_pos -= 15
    c.setFont("Helvetica", 10)
    c.drawString(left_margin, y_pos, "Authorized Signatory")
    
    # ===== EMPLOYEE ACCEPTANCE =====
    y_pos -= 50
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y_pos, "Employee Acceptance:")
    
    y_pos -= 30
    c.setFont("Helvetica", 10)
    c.drawString(left_margin, y_pos, "I hereby accept the revised salary as mentioned above.")
    
    y_pos -= 40
    c.drawString(left_margin, y_pos, "Signature: _______________________")
    c.drawString(left_margin + 250, y_pos, "Date: _______________________")
    
    c.save()
    buffer.seek(0)
    return buffer


def generate_offer_letter_pdf(
    employee_name: str,
    designation: str,
    location: str,
    joining_date: datetime,
    # Annual components
    basic_annual: float,
    hra_annual: float,
    special_allowance_annual: float,
    conveyance_annual: float,
    medical_allowance_annual: float,
    other_allowance_annual: float,
    # Deductions
    professional_tax_annual: float,
    other_deduction_annual: float,
    letter_date: Optional[datetime] = None
) -> io.BytesIO:
    """
    Generate Offer Letter with Salary Annexure PDF
    Combines offer letter content with salary annexure
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    left_margin = 50
    right_margin = width - 50
    
    # ===== GREEN HEADER BAR =====
    c.setFillColor(HEADER_GREEN)
    c.rect(0, height - 30, width, 30, fill=True, stroke=False)
    
    # ===== COMPANY LOGO =====
    logo_x = right_margin - 100
    logo_y = height - 70
    c.setFillColor(HEADER_GREEN)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(logo_x, logo_y, "(")
    c.setFillColor(HEADER_ORANGE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(logo_x + 15, logo_y, "Shekru labs")
    
    # ===== DATE =====
    if letter_date is None:
        letter_date = datetime.now()
    
    date_str = letter_date.strftime("%d %B %Y")
    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, height - 100, f"Date: {date_str}")
    
    # ===== TO SECTION =====
    y_pos = height - 140
    c.setFont("Helvetica", 11)
    c.drawString(left_margin, y_pos, "To,")
    
    y_pos -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y_pos, f"Mr./Ms. {employee_name},")
    
    # ===== SUBJECT =====
    y_pos -= 50
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y_pos, "Sub: Offer of Employment")
    
    # ===== BODY =====
    y_pos -= 40
    c.setFont("Helvetica", 11)
    
    join_date_str = joining_date.strftime("%d %B %Y")
    
    text_width = right_margin - left_margin
    from reportlab.pdfbase.pdfmetrics import stringWidth
    
    body_text = (
        f"We are pleased to offer you the position of {designation} at {COMPANY_NAME}. "
        f"Your employment will commence on {join_date_str}. "
        f"Please find attached the salary annexure with complete compensation details."
    )
    
    words = body_text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = current_line + " " + word if current_line else word
        if stringWidth(test_line, "Helvetica", 11) < text_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    
    for line in lines:
        c.drawString(left_margin, y_pos, line)
        y_pos -= 18
    
    # ===== TERMS =====
    y_pos -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y_pos, "Terms and Conditions:")
    
    y_pos -= 20
    c.setFont("Helvetica", 10)
    terms = [
        "1. This offer is subject to verification of your credentials.",
        "2. You will be on probation for the first 6 months.",
        "3. Notice period of 30 days is applicable.",
        "4. All company policies and code of conduct apply.",
    ]
    
    for term in terms:
        c.drawString(left_margin + 20, y_pos, term)
        y_pos -= 18
    
    # ===== SIGNATURE =====
    y_pos -= 40
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y_pos, "Yours Sincerely,")
    
    y_pos -= 40
    c.drawString(left_margin, y_pos, "For " + COMPANY_NAME)
    
    y_pos -= 50
    c.drawString(left_margin, y_pos, "_______________________")
    y_pos -= 15
    c.setFont("Helvetica", 10)
    c.drawString(left_margin, y_pos, "HR Department")
    
    c.showPage()  # New page for salary annexure
    
    # ===== PAGE 2: SALARY ANNEXURE =====
    # Add salary annexure content on second page
    y_pos = height - 50
    
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y_pos, "Salary Annexure")
    
    y_pos -= 40
    
    # Calculate values
    basic_monthly = round(basic_annual / 12, 2)
    hra_monthly = round(hra_annual / 12, 2)
    special_monthly = round(special_allowance_annual / 12, 2)
    conveyance_monthly = round(conveyance_annual / 12, 2)
    medical_monthly = round(medical_allowance_annual / 12, 2)
    other_monthly = round(other_allowance_annual / 12, 2)
    
    total_ctc_annual = (basic_annual + hra_annual + special_allowance_annual + 
                        conveyance_annual + medical_allowance_annual + other_allowance_annual)
    monthly_ctc = round(total_ctc_annual / 12, 2)
    total_deductions_annual = professional_tax_annual + other_deduction_annual
    monthly_in_hand = round((total_ctc_annual - total_deductions_annual) / 12, 2)
    
    # Employee info
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_margin, y_pos, f"Candidate Name: {employee_name}")
    y_pos -= 18
    c.drawString(left_margin, y_pos, f"Designation: {designation}")
    y_pos -= 18
    c.drawString(left_margin, y_pos, f"Location: {location}")
    
    y_pos -= 30
    
    # Components table header
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_margin, y_pos, "Components")
    c.drawString(left_margin + 200, y_pos, "Per Annum")
    c.drawString(left_margin + 320, y_pos, "Per Month")
    
    y_pos -= 5
    c.line(left_margin, y_pos, right_margin, y_pos)
    
    # Components data
    y_pos -= 18
    c.setFont("Helvetica", 10)
    components = [
        ("Basic", basic_annual, basic_monthly),
        ("HRA", hra_annual, hra_monthly),
        ("Special Allowance", special_allowance_annual, special_monthly),
        ("Conveyance", conveyance_annual, conveyance_monthly),
        ("Medical Allowance", medical_allowance_annual, medical_monthly),
        ("Other", other_allowance_annual, other_monthly),
    ]
    
    for name, annual, monthly in components:
        c.drawString(left_margin, y_pos, name)
        c.drawString(left_margin + 200, y_pos, format_currency_int(annual))
        c.drawString(left_margin + 320, y_pos, format_currency(monthly))
        y_pos -= 18
    
    # Deductions
    y_pos -= 10
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_margin, y_pos, "Deductions")
    y_pos -= 5
    c.line(left_margin, y_pos, right_margin, y_pos)
    y_pos -= 18
    
    c.setFont("Helvetica", 10)
    c.drawString(left_margin, y_pos, "Professional Tax")
    c.drawString(left_margin + 200, y_pos, format_currency_int(professional_tax_annual))
    c.drawString(left_margin + 320, y_pos, "200/month")
    y_pos -= 18
    
    c.drawString(left_margin, y_pos, "Other Deductions")
    c.drawString(left_margin + 200, y_pos, format_currency_int(other_deduction_annual))
    c.drawString(left_margin + 320, y_pos, format_currency(round(other_deduction_annual / 12, 2)))
    
    # CTC Summary
    y_pos -= 30
    c.setFont("Helvetica-Bold", 10)
    c.line(left_margin, y_pos + 5, right_margin, y_pos + 5)
    c.drawString(left_margin, y_pos - 10, f"Total CTC (Annual): {format_currency_int(total_ctc_annual)}")
    c.drawString(left_margin, y_pos - 28, f"Monthly CTC: {format_currency_int(monthly_ctc)}")
    c.drawString(left_margin, y_pos - 46, f"Monthly In-Hand: {format_currency_int(monthly_in_hand)}")
    
    c.save()
    buffer.seek(0)
    return buffer
