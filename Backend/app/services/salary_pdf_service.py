"""
Salary PDF Service - Generate Salary Slip, Increment Letter, and Salary Annexure PDFs
Matches the exact format from provided samples using ReportLab
"""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.lib.units import inch, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, BaseDocTemplate, PageTemplate, Frame
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
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=15,
        bottomMargin=15
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Calculate totals
    total_earnings = basic + hra + special_allowance + medical_allowance + conveyance + other_allowance
    total_deductions = professional_tax + other_deduction
    net_payable = total_earnings - total_deductions
    
    # Page width for calculations
    page_width = landscape(A4)[0] - 40  # minus margins
    
    # Set the col_widths for earnings/deductions and use for both tables
    col_widths = [1.6*inch, 1.5*inch, 1.6*inch, 1.5*inch]
    table_total_width = sum(col_widths)  # Total width for all tables
    
    # ===== HEADER SECTION =====
    # Logo and Address side by side in a table
    address_style = ParagraphStyle(
        'Address',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_RIGHT,
        textColor=BLACK,
    )
    address_parts = COMPANY_ADDRESS.split(", ")
    if len(address_parts) >= 6:
        line_one = ", ".join(address_parts[:3]) + ","
        line_two = ", ".join(address_parts[3:])
        address_html = f"Registered Office:<br/>{line_one}<br/>{line_two}"
    else:
        address_html = f"Registered Office:<br/>{COMPANY_ADDRESS}"
    
    # Prepare logo and address for table
    if USE_LOGO and LOGO_PATH and os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=LOGO_WIDTH * inch, height=LOGO_HEIGHT * 1.2 * inch)
        logo_cell = logo
    else:
        # Fallback to company name if logo not available
        header_style = ParagraphStyle(
            'CompanyHeader',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#4CAF50'),
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
        )
        logo_cell = Paragraph(COMPANY_NAME, header_style)
    
    address_cell = Paragraph(address_html, address_style)
    
    # Create table with logo and address side by side - matching width of tables below
    header_table_data = [[logo_cell, address_cell]]
    header_table = Table(header_table_data, colWidths=[table_total_width * 0.4, table_total_width * 0.6])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),  # Logo left aligned
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),  # Address right aligned
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 1))
    
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
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
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
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
    ]))
    elements.append(emp_name_table)
    
    # ===== EMPLOYEE DETAILS SECTION =====
    col_width = page_width / 2
    details_data = [
        [
            Table([["Employee Id", ":", employee_id]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            Table([["Location", ":", location]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch])
        ],
        [
            Table([["Designation", ":", designation]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            Table([["Working Days", ":", str(working_days)]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch])
        ],
        [
            Table([["DOJ", ":", doj]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            Table([["PF", ":", pf]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch])
        ],
        [
            Table([["PAN", ":", pan]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            Table([["Variable Pay*", ":", format_currency(variable_pay)]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch])
        ],
        [
            Table([["UAN", ":", uan]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            ""
        ],
    ]
    
    # Style for inner tables
    inner_style = TableStyle([
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),  # Label bold
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),  # Colon bold to match label/value
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 0.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ])
    
    for row in details_data:
        for cell in row:
            if isinstance(cell, Table):
                cell.setStyle(inner_style)
    
    details_total_width = sum(col_widths)
    details_table = Table(details_data, colWidths=[details_total_width / 2, details_total_width / 2])
    details_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, BLACK),  # Outer box border
        ('LINEAFTER', (0, 0), (0, -1), 1, BLACK),  # Center vertical line
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 12))
    
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
        ('BOX', (0, 0), (-1, -1), 1, BLACK),  # Outer border
        ('LINEBELOW', (0, 0), (-1, 0), 1, BLACK),  # Line below header
        ('LINEABOVE', (0, -1), (-1, -1), 1, BLACK),  # Line above total row
        ('LINEAFTER', (1, 0), (1, -1), 1, BLACK),  # Center vertical line after earnings column
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
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
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
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
        spaceBefore=4,
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
    # Employer contribution (optional, for CTC calculation)
    employer_pf_annual: float = 0.0,
    variable_pay_annual: float = 0.0,
) -> io.BytesIO:
    """
    Generate Salary Annexure PDF matching the exact sample format.
    
    STRICT CALCULATION RULES:
    1. Total Gross = Basic + HRA + Special Allowance + Medical + Conveyance + Other
    2. Total Earnings = Total Gross
    3. CTC = Total Gross + Employer PF + Variable Pay + PT + Other Tax
    4. Monthly In-Hand = (Total Gross - PT - Other Tax) / 12
    5. Employer PF is part of CTC, NEVER deducted from employee
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
    
    # STRICT RULE: Total Gross = Basic + HRA + Special Allowance + Medical + Conveyance + Other
    total_gross_annual = (basic_annual + hra_annual + special_allowance_annual + 
                          conveyance_annual + medical_allowance_annual + other_allowance_annual)
    monthly_gross = round(total_gross_annual / 12, 2)
    
    # STRICT RULE: CTC = Total Gross + Employer PF + Variable Pay + PT + Other Tax
    ctc_annual = (total_gross_annual + employer_pf_annual + variable_pay_annual + 
                  professional_tax_annual + other_deduction_annual)
    monthly_ctc = round(ctc_annual / 12, 2)
    
    # Employee deductions (Professional Tax + Other Tax)
    total_deductions_annual = professional_tax_annual + other_deduction_annual
    
    # STRICT RULE: Monthly In-Hand = (Total Gross - PT - Other Tax) / 12
    monthly_in_hand = round((total_gross_annual - total_deductions_annual) / 12, 2)
    
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
    # STRICT RULES: Total Gross (earnings) vs CTC (company cost)
    # CTC = Total Gross + Employer PF + Variable Pay + PT + Other Tax
    ctc_data = [
        ["Summary", "Per Annum", "Per Month"],
        ["Total Gross (Earnings):", format_currency_int(total_gross_annual), format_currency_int(monthly_gross)],
        ["Employer PF (12% of Basic):", format_currency_int(employer_pf_annual), format_currency_int(round(employer_pf_annual / 12, 2))],
        ["Total CTC:", format_currency_int(ctc_annual), format_currency_int(monthly_ctc)],
        ["Monthly In-Hand:", "-", format_currency_int(monthly_in_hand)],
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

def _draw_shekru_header(canvas_obj, width, height):
    """
    Draw Shekru Labs professional header matching the exact sample format.
    - Green decorative element in top-left corner (curved/angled shape)
    - "Shekru labs" logo in top-right corner
    """
    # Green decorative shape in top-left corner (triangular/curved element)
    canvas_obj.setFillColor(HEADER_GREEN)
    # Draw a curved green shape at top-left
    path = canvas_obj.beginPath()
    path.moveTo(0, height)
    path.lineTo(0, height - 80)
    path.curveTo(5, height - 60, 15, height - 40, 25, height - 35)
    path.lineTo(35, height)
    path.close()
    canvas_obj.drawPath(path, fill=True, stroke=False)
    
    # Company logo "Shekru labs" in top-right corner
    logo_x = width - 115
    logo_y = height - 35
    
    # Green bracket "("
    canvas_obj.setFillColor(HEADER_GREEN)
    canvas_obj.setFont("Helvetica-Bold", 22)
    canvas_obj.drawString(logo_x, logo_y, "(")
    
    # Orange "Shekru labs" text
    canvas_obj.setFillColor(HEADER_ORANGE)
    canvas_obj.setFont("Helvetica-Bold", 16)
    canvas_obj.drawString(logo_x + 12, logo_y, "Shekru labs")


def _draw_shekru_footer(canvas_obj, width):
    """
    Draw Shekru Labs professional footer with contact information.
    Matches the exact sample format with neutral background, green accent bar,
    and proper icon placement for phone, email, address, website.
    """
    footer_height = 60
    footer_y = 0
    
    # Light gray/neutral footer background
    canvas_obj.setFillColor(colors.HexColor('#F5F5F5'))
    canvas_obj.rect(0, footer_y, width, footer_height, fill=True, stroke=False)
    
    # Green accent bar at top of footer
    canvas_obj.setFillColor(HEADER_GREEN)
    canvas_obj.rect(0, footer_y + footer_height - 4, width, 4, fill=True, stroke=False)
    
    # Green decorative element at bottom-left corner
    path = canvas_obj.beginPath()
    path.moveTo(0, 0)
    path.lineTo(0, 50)
    path.curveTo(5, 35, 15, 20, 25, 15)
    path.lineTo(30, 0)
    path.close()
    canvas_obj.drawPath(path, fill=True, stroke=False)
    
    # Footer text styling
    left_col_x = 55
    right_col_x = width / 2 + 20
    row1_y = footer_y + 38
    row2_y = footer_y + 18
    
    # Phone icon and number (left column, top row)
    canvas_obj.setFillColor(BLACK)
    canvas_obj.circle(left_col_x - 12, row1_y + 2, 7, fill=True)
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica-Bold", 8)
    canvas_obj.drawCentredString(left_col_x - 12, row1_y, "C")
    canvas_obj.setFillColor(BLACK)
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.drawString(left_col_x, row1_y, COMPANY_PHONE)
    
    # Email icon and address (left column, bottom row)
    canvas_obj.setFillColor(BLACK)
    canvas_obj.circle(left_col_x - 12, row2_y + 2, 7, fill=True)
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica-Bold", 7)
    canvas_obj.drawCentredString(left_col_x - 12, row2_y, "@")
    canvas_obj.setFillColor(BLACK)
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.drawString(left_col_x, row2_y, COMPANY_EMAIL)
    
    # Address icon and text (right column, top row - spans 2 lines)
    canvas_obj.setFillColor(BLACK)
    canvas_obj.circle(right_col_x - 12, row1_y + 2, 7, fill=True)
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica-Bold", 8)
    canvas_obj.drawCentredString(right_col_x - 12, row1_y, "O")
    canvas_obj.setFillColor(BLACK)
    canvas_obj.setFont("Helvetica", 8)
    # Split address into two lines
    canvas_obj.drawString(right_col_x, row1_y + 6, "Office 2nd Floor, Manogat Appt., Treasure Park")
    canvas_obj.drawString(right_col_x, row1_y - 6, "Road, Sahakar Nagar, Pune, Maharashtra 411009")
    
    # Website icon and URL (right column, bottom row)
    canvas_obj.setFillColor(BLACK)
    canvas_obj.circle(right_col_x - 12, row2_y + 2, 7, fill=True)
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica-Bold", 7)
    canvas_obj.drawCentredString(right_col_x - 12, row2_y, "W")
    canvas_obj.setFillColor(BLACK)
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.drawString(right_col_x, row2_y, COMPANY_WEBSITE)


def _offer_letter_header_footer(canvas_obj, doc):
    """
    Canvas callback for header and footer on all pages.
    Used with onFirstPage and onLaterPages in BaseDocTemplate.
    """
    canvas_obj.saveState()
    width, height = A4
    _draw_shekru_header(canvas_obj, width, height)
    _draw_shekru_footer(canvas_obj, width)
    canvas_obj.restoreState()


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
    # Employer contribution (optional, for CTC calculation)
    employer_pf_annual: float = 0.0,
    variable_pay_annual: float = 0.0,
    letter_date: Optional[datetime] = None
) -> io.BytesIO:
    """
    Generate Offer Letter with Salary Annexure PDF.
    Uses professional Shekru Labs header/footer on all pages via canvas callbacks.
    
    STRICT CALCULATION RULES:
    1. Total Gross = Basic + HRA + Special Allowance + Medical + Conveyance + Other
    2. Total Earnings = Total Gross
    3. CTC = Total Gross + Employer PF + Variable Pay + PT + Other Tax
    4. Monthly In-Hand = (Total Gross - PT - Other Tax) / 12
    5. Employer PF is part of CTC, NEVER deducted from employee
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth
    
    buffer = io.BytesIO()
    width, height = A4
    
    # Define margins accounting for header/footer space
    left_margin = 50
    right_margin = 40
    top_margin = 70  # Space for header
    bottom_margin = 75  # Space for footer
    
    # Create document with custom page template
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin
    )
    
    # Create frame for content area
    frame = Frame(
        left_margin,
        bottom_margin,
        width - left_margin - right_margin,
        height - top_margin - bottom_margin,
        id='normal'
    )
    
    # Create page template with header/footer callback
    template = PageTemplate(
        id='offer_letter',
        frames=frame,
        onPage=_offer_letter_header_footer
    )
    doc.addPageTemplates([template])
    
    # Build content elements
    elements = []
    styles = getSampleStyleSheet()
    content_width = width - left_margin - right_margin
    
    # Date
    if letter_date is None:
        letter_date = datetime.now()
    date_str = letter_date.strftime("%d %B %Y")
    
    # Date style
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceAfter=20
    )
    elements.append(Paragraph(f"Date: {date_str}", date_style))
    
    # Employee name
    name_style = ParagraphStyle(
        'NameStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceAfter=5
    )
    elements.append(Paragraph(employee_name, name_style))
    
    # Subject - Letter of Appointment (underlined, centered, green)
    subject_style = ParagraphStyle(
        'SubjectStyle',
        parent=styles['Normal'],
        fontSize=14,
        fontName='Helvetica-Bold',
        textColor=HEADER_GREEN,
        alignment=TA_CENTER,
        spaceBefore=15,
        spaceAfter=20
    )
    elements.append(Paragraph('<u>LETTER OF APPOINTMENT</u>', subject_style))
    
    # Greeting
    greeting_style = ParagraphStyle(
        'GreetingStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceAfter=15
    )
    first_name = employee_name.split()[0] if employee_name else "Candidate"
    elements.append(Paragraph(f"Dear {first_name},", greeting_style))
    
    # Body text style (justified)
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica',
        alignment=TA_JUSTIFY,
        spaceAfter=12,
        leading=14
    )
    
    join_date_str = joining_date.strftime("%d %B %Y")
    
    # Introduction paragraph
    intro_text = (
        f"This letter marks an important event in the life of our company and indeed for you. "
        f"We value this letter as a symbol of a new relationship, one that is based on simplicity, "
        f"prudence and humility."
    )
    elements.append(Paragraph(intro_text, body_style))
    
    # Heritage paragraph
    heritage_text = (
        f"When you sign this letter, you will have agreed to uphold our heritage and be a part of the "
        f"<b>{COMPANY_NAME}</b> family. You promise to value our values and be one of us."
    )
    elements.append(Paragraph(heritage_text, body_style))
    
    # Appointment paragraph
    appoint_text = (
        f"We have pleasure in appointing you as <b>{designation}</b> with effect from <b>{join_date_str}</b>, "
        f"or from your date of reporting to work, whichever is earlier, provided that this appointment letter "
        f"shall cease to have effect if you do not report to work by <b>{join_date_str}</b>."
    )
    elements.append(Paragraph(appoint_text, body_style))
    
    # Section header style
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceBefore=15,
        spaceAfter=10
    )
    
    # Probation section
    elements.append(Paragraph("<b>Probation:</b>", section_style))
    
    # Numbered list style
    list_style = ParagraphStyle(
        'ListStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica',
        leftIndent=20,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
        leading=13
    )
    
    probation_items = [
        "1. Your appointment includes a 3-month probation period. Based on your performance and conduct, "
        "this period may be extended or concluded earlier at management's discretion.",
        "2. Absence of leave during the probation period is not allowed."
    ]
    for item in probation_items:
        elements.append(Paragraph(item, list_style))
    
    # Joining Documentation section
    elements.append(Paragraph("<b>Joining Documentations:</b>", section_style))
    
    elements.append(Paragraph("1. Your appointment is subject to your providing the following listed documents:", list_style))
    
    # Sub-list style
    sublist_style = ParagraphStyle(
        'SubListStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica',
        leftIndent=40,
        spaceAfter=4,
        leading=12
    )
    
    doc_items = [
        "a. A relieving letter from your previous employer.",
        "b. Soft copy of the last 3-month pay slip from the previous employer.",
        "c. Soft copy of the last 3-month bank statement salaried from the previous employer.",
        "d. Soft copy of Aadhar card or Passport.",
        "e. Permanent address proof (light bill or property tax receipt.)",
        "f. Soft copy of PAN card",
        "g. Valid email ID & Mobile number",
        "h. Passport size photograph - 4 copies (white background)"
    ]
    for item in doc_items:
        elements.append(Paragraph(item, sublist_style))
    
    # Page break for next section
    elements.append(PageBreak())
    
    # Duties, Responsibilities section
    elements.append(Paragraph("<b>Duties, Responsibilities & Other Employment Clauses:</b>", section_style))
    
    duties_items = [
        "3. Office time is 10:00 AM to 6:00 PM, Monday to Saturday.",
        "4. Employees are expected to follow formal dress code in office premises/client location on week days except on Saturday.",
        "5. You will perform duties as assigned by the company, including any future transfers or promotions.",
        "6. You may work staggered shifts with timings subject to change.",
        "7. Absence without permission or overstaying leave for eight days will be considered voluntary resignation, resulting in the loss of your appointment lien.",
        "8. If you're unable to attend work due to illness, accident, or urgent need, notify Management immediately and provide any required information.",
        f"9. Immediately inform {COMPANY_NAME} of any dishonesty, fraud, or damage to its property that you become aware of."
    ]
    for item in duties_items:
        elements.append(Paragraph(item, list_style))
    
    # Rules, Regulations and Confidentiality
    elements.append(Paragraph("<b>Rules, Regulations and Confidentiality:</b>", section_style))
    
    conf_intro = (
        "10. You will have access to Confidential Information, including proprietary, personal, and sensitive details "
        "about the Company's inventions, products, designs, methods, trade secrets, strategies, software, customer and "
        "employee information, financial data, and more. Treat all such information as confidential, regardless of its form."
    )
    elements.append(Paragraph(conf_intro, list_style))
    
    elements.append(Paragraph("11. <b>You agree to:</b>", list_style))
    
    agree_items = [
        "a. Maintain confidentiality and use information only for its intended purpose.",
        f"b. Not disclose it without {COMPANY_NAME}'s written consent.",
        "c. Treat it with at least reasonable care.",
        "d. Prevent unauthorized use or dissemination.",
        "e. Only copy it when necessary.",
        "f. Do not share it with competitors.",
        "g. Avoid using it for personal or third-party gain.",
        "h. Do not claim ownership of any content or hardware.",
        f"i. Not use it in a way that could harm {COMPANY_NAME}."
    ]
    for item in agree_items:
        elements.append(Paragraph(item, sublist_style))
    
    more_conf_items = [
        f"12. All Confidential Information is {COMPANY_NAME}'s exclusive property, and you are granted no rights to it. "
        f"{COMPANY_NAME} retains full rights to use and exploit its Confidential Information.",
        f"13. If required to disclose Confidential Information by court or government order, notify {COMPANY_NAME} promptly "
        f"and cooperate fully ({COMPANY_NAME} bears reasonable expenses) in opposing or limiting the disclosure.",
        f"14. Upon leaving {COMPANY_NAME} or upon request, return or destroy (at {COMPANY_NAME}'s option) all Confidential "
        "Information and confirm this in writing if requested.",
        "15. During and after employment, do not disclose or use Confidential Information except as required for your duties or by law.",
        "16. Breaching this clause may result in disciplinary action, including termination without notice.",
        "17. Maintain the confidentiality of price-sensitive information, sharing only on a need-to-know basis. Do not use this "
        "information for trading or recommendations. Adhere to trading restrictions during your employment."
    ]
    for item in more_conf_items:
        elements.append(Paragraph(item, list_style))
    
    # Page break
    elements.append(PageBreak())
    
    # Intellectual Property
    elements.append(Paragraph("<b>Intellectual Property:</b>", section_style))
    
    ip_items = [
        "18. Intellectual Property Rights include all industrial and intellectual property rights such as patents, trademarks, "
        "copyrights, trade secrets, software, and more.",
        f"19. You confirm your work for {COMPANY_NAME} will be original and not infringe on third-party rights. If {COMPANY_NAME} "
        f"faces claims due to your work, you agree to indemnify {COMPANY_NAME}.",
        f"20. Any intellectual property created by you during your employment, related to {COMPANY_NAME}'s business, tasks assigned, "
        f"or using {COMPANY_NAME} resources, will be {COMPANY_NAME}'s property. You must disclose these developments to {COMPANY_NAME} immediately.",
        f"21. You assign all rights to such developments to {COMPANY_NAME} without additional compensation, acknowledging your salary "
        "is adequate for this assignment.",
        f"22. This assignment is perpetual and irrevocable, even if {COMPANY_NAME} does not exploit the developments commercially.",
        f"23. This assignment includes moral rights, which you waive. If unenforceable, you grant {COMPANY_NAME} an exclusive, "
        "perpetual, royalty-free license to use the developments.",
        f"24. If asked to assist with intellectual property matters after your employment, {COMPANY_NAME} will compensate you for "
        "your time at your previous hourly rate.",
        f"25. If you cannot sign the necessary documents for intellectual property rights, you appoint {COMPANY_NAME} as your agent "
        "to act on your behalf.",
        f"26. You are also bound by {COMPANY_NAME}'s Intellectual Property policy."
    ]
    for item in ip_items:
        elements.append(Paragraph(item, list_style))
    
    # Conflict of Interest
    elements.append(Paragraph("<b>Conflict of Interest:</b>", section_style))
    
    conflict_items = [
        f"27. During employment, you will not engage in any competing business activities or compete with {COMPANY_NAME}'s products or services.",
        f"28. You will not undertake any other employment or business while employed with {COMPANY_NAME}.",
        f"29. Immediately inform {COMPANY_NAME} of any potential or actual conflict of interest, and comply with {COMPANY_NAME}'s directions to resolve it.",
        f"30. Do not accept any gratuity, payment, or benefit from anyone doing or intending to do business with {COMPANY_NAME}.",
        f"31. Use {COMPANY_NAME} resources ethically, ensuring it does not interfere with your duties or contradict {COMPANY_NAME}'s interests."
    ]
    for item in conflict_items:
        elements.append(Paragraph(item, list_style))
    
    # Page break
    elements.append(PageBreak())
    
    # Leave and WFH policies
    elements.append(Paragraph("<b>Leave and work from home policies:</b>", section_style))
    
    leave_items = [
        "32. Employees must adhere to the company's designated calendar for leave requests as outlined in company policies.",
        "33. Total paid leaves per financial year are 12. Which include 07 casual leaves and 05 sick leaves.",
        "34. Only 05 leaves can be encashed or carried forward for next financial year.",
        "35. Requests for leave must be submitted at least 24 hours in advance, following company policy and procedures.",
        "36. Working on Sundays may entitle employees to extra benefits as per respective salary structure.",
        "37. Employees are permitted to work from home for up to 04 days in each month as per company policy."
    ]
    for item in leave_items:
        elements.append(Paragraph(item, list_style))
    
    # Miscellaneous
    elements.append(Paragraph("<b>Miscellaneous:</b>", section_style))
    
    misc_items = [
        f"38. Notices: All employment-related notices shall be in writing and in English, delivered by hand, registered post, "
        f"email, courier, or speed post. You must update {COMPANY_NAME} of any address or contact detail changes.",
        "39. Severability: If any provision of this Letter is deemed invalid, the remaining provisions shall remain valid and enforceable.",
        f"40. Publicity: You cannot use {COMPANY_NAME}'s name or trademarks in a manner detrimental to {COMPANY_NAME}'s image "
        f"without prior written consent. Any articles mentioning {COMPANY_NAME} require {COMPANY_NAME}'s approval.",
        f"41. Non-Disparagement: You agree not to make false, defamatory, or disparaging statements about {COMPANY_NAME}, its employees, officers, or directors.",
        "42. Waiver: No delay or failure in exercising any rights shall be a waiver. Any waiver must be in writing and signed by an authorized representative.",
        "43. Integration: This Letter and its Exhibit constitute the entire agreement, superseding all previous agreements between the Parties."
    ]
    for item in misc_items:
        elements.append(Paragraph(item, list_style))
    
    # Page break for Salary Annexure
    elements.append(PageBreak())
    
    # ===== SALARY ANNEXURE PAGE =====
    annexure_title_style = ParagraphStyle(
        'AnnexureTitle',
        parent=styles['Heading1'],
        fontSize=16,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceAfter=30
    )
    elements.append(Paragraph("Salary Annexure", annexure_title_style))
    
    # Calculate monthly values
    basic_monthly = round(basic_annual / 12, 2)
    hra_monthly = round(hra_annual / 12, 2)
    special_monthly = round(special_allowance_annual / 12, 2)
    conveyance_monthly = round(conveyance_annual / 12, 2)
    medical_monthly = round(medical_allowance_annual / 12, 2)
    other_monthly = round(other_allowance_annual / 12, 2)
    
    # STRICT RULE: Total Gross = Basic + HRA + Special Allowance + Medical + Conveyance + Other
    total_gross_annual = (basic_annual + hra_annual + special_allowance_annual + 
                          conveyance_annual + medical_allowance_annual + other_allowance_annual)
    monthly_gross = round(total_gross_annual / 12, 2)
    
    # STRICT RULE: CTC = Total Gross + Employer PF + Variable Pay + PT + Other Tax
    ctc_annual = (total_gross_annual + employer_pf_annual + variable_pay_annual + 
                  professional_tax_annual + other_deduction_annual)
    monthly_ctc = round(ctc_annual / 12, 2)
    
    # Employee deductions (Professional Tax + Other Tax)
    total_deductions_annual = professional_tax_annual + other_deduction_annual
    
    # STRICT RULE: Monthly In-Hand = (Total Gross - PT - Other Tax) / 12
    monthly_in_hand = round((total_gross_annual - total_deductions_annual) / 12, 2)
    
    # Employee info table
    info_data = [
        ["Company Name:", COMPANY_NAME],
        ["Candidate Name:", f"<b>{employee_name}</b>"],
        ["Designation:", f"<b>{designation}</b>"],
        ["Location:", f"<b>{location}</b>"],
    ]
    
    # Convert to Paragraphs for bold support
    info_table_data = []
    for row in info_data:
        info_table_data.append([
            Paragraph(row[0], ParagraphStyle('InfoLabel', fontName='Helvetica-Bold', fontSize=10)),
            Paragraph(row[1], ParagraphStyle('InfoValue', fontName='Helvetica', fontSize=10))
        ])
    
    info_table = Table(info_table_data, colWidths=[2*inch, content_width - 2*inch])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))
    
    # Salary Components table
    col_widths = [2.5*inch, 1.3*inch, 1.3*inch]
    
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
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
    ]))
    elements.append(components_table)
    elements.append(Spacer(1, 10))
    
    # Deductions table
    pt_monthly_note = "PM 200 In Feb 300" if professional_tax_annual > 0 else "-"
    
    deductions_data = [
        ["Deductions Amount(B)", "Per Annum", "Per Month"],
        ["Professional Tax Deduction", format_currency_int(professional_tax_annual), pt_monthly_note],
        ["Other", format_currency_int(other_deduction_annual), format_currency(round(other_deduction_annual / 12, 2))],
    ]
    
    deductions_table = Table(deductions_data, colWidths=col_widths)
    deductions_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
    ]))
    elements.append(deductions_table)
    elements.append(Spacer(1, 10))
    
    # CTC Summary table - STRICT RULES: Total Gross vs CTC
    # CTC = Total Gross + Employer PF + Variable Pay + PT + Other Tax
    ctc_data = [
        ["Summary", "Per Annum", "Per Month"],
        ["Total Gross (Earnings):", format_currency_int(total_gross_annual), format_currency_int(monthly_gross)],
        ["Employer PF (12% of Basic):", format_currency_int(employer_pf_annual), format_currency_int(round(employer_pf_annual / 12, 2))],
        ["Total CTC:", format_currency_int(ctc_annual), format_currency_int(monthly_ctc)],
        ["Monthly In-Hand:", "-", format_currency_int(monthly_in_hand)],
    ]
    
    ctc_table = Table(ctc_data, colWidths=col_widths)
    ctc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
    ]))
    elements.append(ctc_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
