"""
Salary PDF Service - Generate Salary Slip, Increment Letter, and Salary Annexure PDFs
Matches the exact format from provided samples using ReportLab
"""
import io
from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.lib.units import inch, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, BaseDocTemplate, PageTemplate, Frame, KeepTogether
from reportlab.pdfgen import canvas
from typing import List, Optional, Tuple
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
    pf_no: str = "",
    payment_mode: str = "Bank Transfer",
    bank_name: str = "",
    bank_account: str = "",
    custom_deductions: Optional[List[Tuple[str, float]]] = None,
) -> io.BytesIO:
    """
    Generate Salary Slip PDF matching the exact sample format
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=10,
        leftMargin=10,
        topMargin=15,
        bottomMargin=15
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Add spacing at the top to move content down for consistency
    elements.append(Spacer(1, 20))
    
    # Calculate totals
    total_earnings = basic + hra + special_allowance + medical_allowance + conveyance + other_allowance
    # Parse pf (may be string like "3,102.83" or numeric); include in total deductions
    pf_numeric = 0.0
    try:
        if pf is not None and str(pf).strip().upper() not in ("", "NA", "-"):
            pf_numeric = float(str(pf).replace(",", ""))
    except Exception:
        pf_numeric = 0.0

    # Show PF amount/parameters in slip only when PF No exists.
    show_pf = bool(pf_no and str(pf_no).strip() and str(pf_no).strip().upper() not in ("NA", "N/A", ""))
    if not show_pf:
        pf_numeric = 0.0

    custom_extra = 0.0
    custom_rows: List[Tuple[str, float]] = []
    if custom_deductions:
        for raw_label, raw_amt in custom_deductions:
            lbl = str(raw_label).strip()
            if not lbl or raw_amt is None or float(raw_amt) <= 0:
                continue
            amt = round(float(raw_amt), 2)
            custom_extra += amt
            # Plain-text cell; truncate very long labels
            custom_rows.append((lbl[:120], amt))

    # Employee deductions for "Net Payable"
    employee_total_deductions = professional_tax + other_deduction + pf_numeric + custom_extra
    total_deductions = professional_tax + other_deduction + pf_numeric + custom_extra
    # Variable pay should only affect "Total Net Payable" when it has a value.
    variable_pay_amount = float(variable_pay) if variable_pay else 0.0
    net_payable = (total_earnings + variable_pay_amount) - employee_total_deductions
    
    # Page width for calculations
    page_width = landscape(A4)[0] - 40  # minus margins
    
    # Set the col_widths for earnings/deductions and use for both tables
    col_widths = [1.8*inch, 1.8*inch, 1.8*inch, 1.8*inch]
    table_total_width = sum(col_widths)  # Total width for all tables
    
    # ===== HEADER SECTION =====
    # Logo and Address side by side in a table
    address_style = ParagraphStyle(
        'Address',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_LEFT,
        textColor=BLACK,
    )
    # Use the full address without forcing <br/> line breaks so ReportLab can
    # wrap the text naturally within the available column width.
    # Put company name above the registered address
    address_html = f"<b>Shekru Labs India Pvt. Ltd.</b><br/>Registered Address: <br/>{COMPANY_ADDRESS}"
    
    # Prepare logo and address for table
    if USE_LOGO and LOGO_PATH and os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=LOGO_WIDTH * inch, height=LOGO_HEIGHT * 0.35 * inch)
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
        ('BOX', (0, 0), (-1, -1), 1, BLACK),  # Outer box border
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),  # Logo left aligned
        # Address cell: left-align text but add left padding so the text starts
        # from the center margin of the overall header box (i.e., shift right).
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (0, -1), 8),  # Left padding for logo column
        ('RIGHTPADDING', (0, 0), (0, -1), 10),  # Right padding for logo column (spacing between columns)
        # Shift the address start so the text begins at the centre margin of
        # the overall header (same visual starting point as the employee details section).
        ('LEFTPADDING', (1, 0), (1, -1), table_total_width * 0.1 + 8),
        ('RIGHTPADDING', (1, 0), (1, -1), 8),  # Right padding for address column
    ]))
    elements.append(header_table)
    
    # ===== PAYSLIP HEADER BAR =====
    month_name = get_month_name(month)
    payslip_header = [[f"Payslip For the Month of {month_name}- {year}"]]
    payslip_header_table = Table(payslip_header, colWidths=[sum(col_widths)])
    payslip_header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GRAY_BG),
        ('TEXTCOLOR', (0, 0), (-1, -1), BLACK),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 1, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
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
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
    ]))
    elements.append(emp_name_table)
    
    # ===== EMPLOYEE DETAILS SECTION =====
    col_width = page_width / 2
    wrap_value_style = ParagraphStyle(
        "WrapValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=12,
        wordWrap="CJK",  # allows breaking long tokens (no spaces)
    )
    
    # Build details_data conditionally - only show UAN and PF No if they exist
    details_data = [
        [
            Table([["Employee Id", ":", employee_id]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            Table([["Location", ":", location]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
        ],
        [
            Table([["Designation", ":", designation]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            Table([["Working Days", ":", str(working_days)]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
        ],
    ]
    
    # Add DOJ row - pair with UAN if exists, else Variable Pay (move Variable Pay up when UAN hidden)
    has_uan = bool(uan and uan.strip() and uan.upper() not in ("NA", "N/A", ""))
    if has_uan:
        details_data.append([
            Table([["DOJ", ":", doj]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            Table([["UAN", ":", uan]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
        ])
    else:
        details_data.append([
            Table([["DOJ", ":", doj]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            Table([["Variable Pay*", ":", format_currency(variable_pay)]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
        ])
    
    # Add PAN row - pair with PF No only if PF No exists
    pf_no_wrapped = None
    if pf_no and pf_no.strip() and pf_no.upper() not in ("NA", "N/A", ""):
        pf_no_wrapped = Paragraph(_xml_escape(str(pf_no)), wrap_value_style)
        details_data.append([
            Table([["PAN", ":", pan]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            Table([["PF No.", ":", pf_no_wrapped]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
        ])
    else:
        details_data.append([
            Table([["PAN", ":", pan]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            "",
        ])
    
    # Bank details (omit rows when values are missing)
    has_bank_name = bool(bank_name and str(bank_name).strip() and str(bank_name).strip().upper() not in ("NA", "N/A", ""))
    has_bank_account = bool(
        bank_account and str(bank_account).strip() and str(bank_account).strip().upper() not in ("NA", "N/A", "")
    )

    # When UAN is visible, Variable Pay is shown on the right in this section.
    if has_uan:
        left_cell = (
            Table([["Bank Name", ":", str(bank_name).strip()]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch])
            if has_bank_name
            else ""
        )
        details_data.append([
            left_cell,
            Table([["Variable Pay*", ":", format_currency(variable_pay)]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
        ])
    else:
        # UAN not visible: Variable Pay already shown next to DOJ. Only show Bank Name if present.
        if has_bank_name:
            details_data.append([
                Table([["Bank Name", ":", str(bank_name).strip()]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
                "",
            ])

    if has_bank_account:
        details_data.append([
            Table([["Bank A/C No.", ":", str(bank_account).strip()]], colWidths=[1.2*inch, 0.1*inch, col_width - 1.5*inch]),
            "",
        ])
    
    # Style for inner tables
    inner_style = TableStyle([
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),  # Label bold
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),  # Colon bold to match label/value
        ('FONTSIZE', (0, 0), (-1, -1), 11),
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
    
    # Data rows - align earnings and deductions side by side (no blank rows in either column).
    # PF label/amount only when PF No exists and amount > 0
    if show_pf and pf_numeric and pf_numeric > 0:
        pf_display = format_currency(pf_numeric)
        pf_label = "PF"
    else:
        pf_display = ""
        pf_label = ""

    def _pair_optional_deduction(idx: int) -> Tuple[str, str]:
        """Return (label, formatted amount) for optional deduction slot idx, or empty strings."""
        if idx >= len(custom_rows):
            return "", ""
        lbl, amt = custom_rows[idx]
        lbl = str(lbl).strip()
        if not lbl or amt is None or float(amt) <= 0:
            return "", ""
        return lbl[:120], format_currency(float(amt))

    # Pair optional deductions with fixed earnings rows so the earnings column has no gaps:
    # - With PF: optional[0..2] sit on Medical / Conveyance / Other Allowance rows (under PF).
    # - Without PF: optional[0] on Special row (under Other), optional[1..2] on Medical / Conveyance.
    if show_pf:
        earnings_deductions_data = [
            ["Basic", format_currency(basic), "Professional Tax", format_currency(professional_tax)],
            ["House Rent Allowance", format_currency(hra), "Other", format_currency(other_deduction)],
            ["Special Allowance", format_currency(special_allowance), pf_label, pf_display],
            [
                "Medical Allowance",
                format_currency(medical_allowance),
                *_pair_optional_deduction(0),
            ],
            [
                "Conveyance Allowance",
                format_currency(conveyance),
                *_pair_optional_deduction(1),
            ],
            [
                "Other Allowance",
                format_currency(other_allowance),
                *_pair_optional_deduction(2),
            ],
        ]
    else:
        earnings_deductions_data = [
            ["Basic", format_currency(basic), "Professional Tax", format_currency(professional_tax)],
            ["House Rent Allowance", format_currency(hra), "Other", format_currency(other_deduction)],
            [
                "Special Allowance",
                format_currency(special_allowance),
                *_pair_optional_deduction(0),
            ],
            [
                "Medical Allowance",
                format_currency(medical_allowance),
                *_pair_optional_deduction(1),
            ],
            [
                "Conveyance Allowance",
                format_currency(conveyance),
                *_pair_optional_deduction(2),
            ],
            ["Other Allowance", format_currency(other_allowance), "", ""],
        ]
    
    # Total row
    total_row = [["Total Earnings", format_currency(total_earnings), "Total Deductions", format_currency(total_deductions)]]
    
    # Combine all
    full_table_data = earnings_header + earnings_deductions_data + total_row
    
    col_widths = [1.8*inch, 1.8*inch, 1.8*inch, 1.8*inch]
    earnings_table = Table(full_table_data, colWidths=col_widths)
    earnings_table.setStyle(TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (1, 0), GRAY_BG),
        ('BACKGROUND', (2, 0), (3, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        # Header alignment: labels left, amount headers right
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('ALIGN', (2, 0), (2, 0), 'LEFT'),
        ('ALIGN', (3, 0), (3, 0), 'RIGHT'),
        
        # Header font size (keep as-is)
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        # Data rows: 10pt regular
        ('FONTSIZE', (0, 1), (-1, -2), 11),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('ALIGN', (1, 1), (1, -2), 'RIGHT'),
        ('ALIGN', (3, 1), (3, -2), 'RIGHT'),
        # Total row styling - keep font size same as header
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        # Total row alignment: labels left, amounts right
        ('ALIGN', (0, -1), (0, -1), 'LEFT'),
        ('ALIGN', (1, -1), (1, -1), 'RIGHT'),
        ('ALIGN', (2, -1), (2, -1), 'LEFT'),
        ('ALIGN', (3, -1), (3, -1), 'RIGHT'),
        
        # Total row styling
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (1, -1), LIGHT_GRAY),
        ('BACKGROUND', (2, -1), (3, -1), LIGHT_GRAY),
        
        # Grid
        ('BOX', (0, 0), (-1, -1), 1, BLACK),  # Outer border
        ('LINEBELOW', (0, 0), (-1, 0), 1, BLACK),  # Line below header
        ('LINEABOVE', (0, -1), (-1, -1), 1, BLACK),  # Line above total row
        ('LINEAFTER', (1, 0), (1, -1), 1, BLACK),  # Center vertical line after earnings column
        # Different vertical padding for header, data rows and total row
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 1), (-1, -2), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -2), 3),
        ('TOPPADDING', (0, -1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 6),
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
        ('FONTSIZE', (0, 0), (-1, -1), 11),
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


def _build_salary_annexure_elements(
    employee_name: str,
    designation: str,
    location: str,
    basic_annual: float,
    hra_annual: float,
    special_allowance_annual: float,
    conveyance_annual: float,
    medical_allowance_annual: float,
    other_allowance_annual: float,
    professional_tax_annual: float,
    other_deduction_annual: float,
    employer_pf_annual: float = 0.0,
    variable_pay_annual: float = 0.0,
) -> list:
    """
    Generate Salary Annexure PDF matching the exact sample format.
    
    STRICT CALCULATION RULES:
    1. Total Gross = Basic + HRA + Special Allowance + Medical + Conveyance + Other
    2. Total Earnings = Total Gross
    3. CTC = Total Gross + Employer PF + PT + Other Tax
    4. Monthly In-Hand = (Total Gross - PT - Other Tax - PF) / 12
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
    
    # STRICT RULE: CTC = Total Gross + Employer PF + PT + Other Tax
    ctc_annual = (
        total_gross_annual + employer_pf_annual + professional_tax_annual + other_deduction_annual
    )
    monthly_ctc = round(ctc_annual / 12, 2)
    
    # Employee deductions (Professional Tax + Other Tax + PF)
    total_deductions_annual = professional_tax_annual + other_deduction_annual + employer_pf_annual
    
    # STRICT RULE: Monthly In-Hand = (Total Gross - PT - Other Tax - PF) / 12
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
    
    # Reuse consistent widths across all tables in this section
    col_widths = [2.8*inch, 1.5*inch, 1.5*inch]
    table_total_width = sum(col_widths)  # Total width: 5.8*inch
    
    # ===== EMPLOYEE INFO TABLE =====
    info_data = [
        ["Company Name:", COMPANY_NAME],
        ["Candidate Name:", employee_name],
        ["Designation:", designation],
        ["Location:", "Pune"],
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, table_total_width - 2*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 1, BLACK),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))
    
    # ===== SALARY COMPONENTS TABLE =====
    # Components section
    components_data = [
        ["A) Fixed Gross Salary", "Per Annum", "Per Month"],
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
        ('FONTSIZE', (0, 0), (-1, -1), 11),
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
        ["B) Employee Contribution", "Per Annum", "Per Month"],
        ["Professional Tax Deduction", format_currency_int(professional_tax_annual), pt_monthly_note],
        ["Other", format_currency_int(other_deduction_annual), format_currency(round(other_deduction_annual / 12, 2))],
        ["PF", format_currency_int(employer_pf_annual), format_currency(round(employer_pf_annual / 12, 2))],
        ["Variable Pay", format_currency_int(variable_pay_annual), format_currency(round(variable_pay_annual / 12, 2))],
    ]
    
    deductions_table = Table(deductions_data, colWidths=col_widths)
    deductions_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Data
        ('FONTSIZE', (0, 0), (-1, -1), 11),
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
    # CTC = Total Gross + Employer PF + PT + Other Tax
    # Keep header row (Per Annum / Per Month) and present A/B/CTC rows
    employee_contribution_annual = professional_tax_annual + other_deduction_annual + employer_pf_annual
    ctc_data = [
        ["", "Per Annum", "Per Month"],
        ["A) Gross Salary", format_currency_int(total_gross_annual), format_currency(monthly_gross)],
        ["B) Employee Contribution", format_currency_int(employee_contribution_annual), format_currency(round(employee_contribution_annual / 12, 2))],
        ["Total Cost To Company (CTC):", format_currency_int(ctc_annual), format_currency(monthly_ctc)],
    ]
    
    ctc_table = Table(ctc_data, colWidths=col_widths)
    ctc_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Data
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 1, BLACK),
    ]))
    elements.append(ctc_table)
    
    return elements


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
    
    Display Logic:
    - Total Gross = Sum of all earnings (employee receives this)
    - CTC = Total Gross + Employer PF
    - Monthly In-Hand = (Total Gross - Employee Deductions) / 12
    """
    buffer = io.BytesIO()
    width, height = A4
    left_margin = 50
    right_margin = 50  # Equal to left_margin for symmetric table spacing
    top_margin = 100   # header space (extra room between header and content)
    bottom_margin = 75  # footer space

    # Switch to BaseDocTemplate like offer_letter
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin
    )
    frame = Frame(
        left_margin,
        bottom_margin,
        width - left_margin - right_margin,
        height - top_margin - bottom_margin,
        id='normal_annexure'
    )
    template = PageTemplate(
        id='annexure',
        frames=frame,
        onPage=_offer_letter_header_footer
    )
    doc.addPageTemplates([template])

    # Use the helper function to build salary annexure elements
    elements = _build_salary_annexure_elements(
        employee_name, designation, location,
        basic_annual, hra_annual, special_allowance_annual,
        conveyance_annual, medical_allowance_annual, other_allowance_annual,
        professional_tax_annual, other_deduction_annual,
        employer_pf_annual, variable_pay_annual
    )
    
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
    letter_date: Optional[datetime] = None,
    title: Optional[str] = None,
    # Optional salary annexure parameters
    include_salary_annexure: bool = False,
    basic_annual: float = 0.0,
    hra_annual: float = 0.0,
    special_allowance_annual: float = 0.0,
    conveyance_annual: float = 0.0,
    medical_allowance_annual: float = 0.0,
    other_allowance_annual: float = 0.0,
    professional_tax_annual: float = 0.0,
    other_deduction_annual: float = 0.0,
    employer_pf_annual: float = 0.0,
    variable_pay_annual: float = 0.0,
) -> io.BytesIO:
    """
    Generate Increment Letter PDF matching the exact sample format.
    Optionally includes salary annexure as second page.
    """
    buffer = io.BytesIO()
    width, height = A4
    
    # Margins
    left_margin = 50
    right_margin = 50
    top_margin = 100
    bottom_margin = 75
    
    # Use BaseDocTemplate for multi-page support and consistent header/footer
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin
    )
    frame = Frame(
        left_margin,
        bottom_margin,
        width - left_margin - right_margin,
        height - top_margin - bottom_margin,
        id='normal'
    )
    template = PageTemplate(
        id='increment_letter',
        frames=frame,
        onPage=_offer_letter_header_footer
    )
    doc.addPageTemplates([template])
    
    elements = []
    styles = getSampleStyleSheet()
    
    # ===== DATE =====
    if letter_date is None:
        letter_date = datetime.now()
    
    date_str = letter_date.strftime("%d %B %Y")
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceAfter=20
    )
    elements.append(Paragraph(f"Date: {date_str}", date_style))
    
    # ===== TO SECTION =====
    to_style = ParagraphStyle(
        'ToStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica',
        spaceAfter=5
    )
    elements.append(Paragraph("To,", to_style))
    
    name_style = ParagraphStyle(
        'NameStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceAfter=5
    )
    # Title handling: allow optional title override (Mr, Mrs, Miss). Default was previously "Mr."
    title_map = {'Mr': 'Mr.', 'Mrs': 'Mrs.', 'Miss': 'Miss'}
    display_title = title_map.get(title, 'Mr.')
    elements.append(Paragraph(f"{display_title} {employee_name},", name_style))
    
    designation_style = ParagraphStyle(
        'DesignationStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica',
        spaceAfter=30
    )
    elements.append(Paragraph(f"{designation}, {location}.", designation_style))
    
    # ===== SUBJECT =====
    subject_style = ParagraphStyle(
        'SubjectStyle',
        parent=styles['Normal'],
        fontSize=14,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceAfter=20
    )
    elements.append(Paragraph("Sub: Letter of Increment", subject_style))
    
    # ===== GREETING =====
    first_name = employee_name.split()[0] if employee_name else "Employee"
    greeting_style = ParagraphStyle(
        'GreetingStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceAfter=15
    )
    elements.append(Paragraph(f"Dear {first_name},", greeting_style))
    
    # ===== BODY TEXT =====
    eff_day = ordinal(effective_date.day)
    eff_month = effective_date.strftime("%B")
    eff_year = effective_date.year
    
    body_text = (
        f"We are pleased to inform you that after evaluating your performance we are your monthly salary "
        f"has been revised w.e.f {eff_day} {eff_month} {eff_year}, and the new salary structure will be:"
    )
    
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica',
        alignment=TA_LEFT,
        spaceAfter=10,
        leading=14
    )
    elements.append(Paragraph(body_text, body_style))
    
    # ===== SALARY DETAILS =====
    # Slightly tighter spacing between salary lines
    salary_style = ParagraphStyle(
        'SalaryStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceAfter=4,
        leading=14
    )
    elements.append(Paragraph(f"Previous Salary: {format_currency(previous_salary)}/-", salary_style))
    elements.append(Paragraph(f"Increment: {format_currency(increment_amount)}/-", salary_style))
    elements.append(Paragraph(f"New Salary: {format_currency(new_salary)}/-", salary_style))
    # Extra spacing before closing paragraph to separate sections
    elements.append(Spacer(1, 14))
    
    # ===== CLOSING PARAGRAPH =====
    closing_text = (
        "For remaining salary breakup details and other terms and conditions please contact the HR "
        "department. We look forward to your valuable contributions to the organization and wishing "
        "you a great career ahead. Please sign the duplicate copy of this letter as a token of acceptance of "
        "the same."
    )
    
    closing_style = ParagraphStyle(
        'ClosingStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica',
        alignment=TA_LEFT,
        spaceAfter=20,
        leading=14
    )
    elements.append(Paragraph(closing_text, closing_style))
    
    # ===== SIGNATURE SECTION =====
    elements.append(Spacer(1, 20))
    
    signature_style = ParagraphStyle(
        'SignatureStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceAfter=5
    )
    elements.append(Paragraph("Yours Sincerely,", signature_style))
    
    company_style = ParagraphStyle(
        'CompanyStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceAfter=40
    )
    elements.append(Paragraph("For " + COMPANY_NAME, company_style))
    
    line_style = ParagraphStyle(
        'LineStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica',
        spaceAfter=8
    )
    elements.append(Paragraph("_______________________", line_style))
    
    signatory_style = ParagraphStyle(
        'SignatoryStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica',
        spaceAfter=15
    )
    elements.append(Paragraph("Authorized Signatory", signatory_style))
    
    acceptance_style = ParagraphStyle(
        'AcceptanceStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceAfter=15
    )
    elements.append(Paragraph("Employee Acceptance:", acceptance_style))
    
    acceptance_text_style = ParagraphStyle(
        'AcceptanceTextStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica',
        spaceAfter=20
    )
    elements.append(Paragraph("I hereby accept the revised salary as mentioned above.", acceptance_text_style))
    
    # Signature and date line
    signature_line_data = [
        ["Signature: _______________________", "Date: _______________________"]
    ]
    # Ensure the signature table itself is left-aligned with the page content
    signature_table = Table(signature_line_data, colWidths=[3*inch, 3*inch], hAlign='LEFT')
    signature_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        # Remove default padding so text aligns with left margin of other paragraphs
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),  # Signature column left-aligned
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),  # Date column right-aligned
    ]))
    elements.append(signature_table)
    
    # If salary annexure is requested, add a page break and append annexure elements
    if include_salary_annexure:
        elements.append(PageBreak())
        annexure_elements = _build_salary_annexure_elements(
            employee_name, designation, location,
            basic_annual, hra_annual, special_allowance_annual,
            conveyance_annual, medical_allowance_annual, other_allowance_annual,
            professional_tax_annual, other_deduction_annual,
            employer_pf_annual, variable_pay_annual
        )
        elements.extend(annexure_elements)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

def _draw_shekru_header(canvas_obj, width, height):
    """
    Draw Shekru Labs professional header.
    For offer letters we now use the official logo image from Backend/assets/logo.png
    instead of the text-based logo. If the image is not found, we fall back to the
    previous text logo to avoid breaking PDF generation.
    """
    # Green header bars on the left/top, matching the newer design:
    #  - A wide top bar with an angled cut on the right
    #  - A thinner bar below, also with an angled right edge
    canvas_obj.setFillColor(HEADER_GREEN)
    # Slimmer bars with shorter reach to the right so they don't overlap the logo
    # Cuts are inverse and symmetrical between the two bars
    top_bar_height = 35
    second_bar_height = 14
    # Make diagonal angles match visually
    top_bar_cut_width = 240  # upper bar length
    second_bar_cut_width = 320  # lower bar length
    slant_offset = 8  # pixels (lower bar horizontal run)
    # Calculate top bar's slant offset so angles match
    top_slant_offset = int(top_bar_height * slant_offset / second_bar_height)

    # Top wide bar
    top_path = canvas_obj.beginPath()
    top_path.moveTo(0, height - top_bar_height)
    top_path.lineTo(width - top_bar_cut_width, height - top_bar_height)
    top_path.lineTo(width - top_bar_cut_width + top_slant_offset, height)
    top_path.lineTo(0, height)
    top_path.close()
    canvas_obj.drawPath(top_path, fill=True, stroke=False)

    # Second, thinner bar
    bar_gap = 14
    second_y_top = height - top_bar_height - bar_gap
    second_y_bottom = second_y_top - second_bar_height
    second_path = canvas_obj.beginPath()
    second_path.moveTo(0, second_y_bottom)
    second_path.lineTo(width - second_bar_cut_width, second_y_bottom)
    second_path.lineTo(width - second_bar_cut_width + slant_offset, second_y_top)
    second_path.lineTo(0, second_y_top)
    second_path.close()
    canvas_obj.drawPath(second_path, fill=True, stroke=False)
    
    # Try to draw the logo image from Backend/assets/logo.png (project root based)
    try:
        backend_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        logo_path = os.path.join(backend_root, "assets", "logo.png")
        
        if os.path.exists(logo_path):
            # Position logo in top-right, with reasonable size and aspect ratio preserved
            # Slightly larger logo for better visibility in offer letters
            logo_width = 170
            logo_height = 70
            logo_x = width - logo_width - 40
            logo_y = height - logo_height - 10
            canvas_obj.drawImage(
                logo_path,
                logo_x,
                logo_y,
                width=logo_width,
                height=logo_height,
                preserveAspectRatio=True,
                mask="auto",
            )
            return
    except Exception:
        # If anything goes wrong, silently fall back to text-based logo below
        pass
    
    # Fallback: draw the original text-based "Shekru labs" logo
    logo_x = width - 115
    logo_y = height - 35
    canvas_obj.setFillColor(HEADER_GREEN)
    canvas_obj.setFont("Helvetica-Bold", 22)
    canvas_obj.drawString(logo_x, logo_y, "(")
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
    canvas_obj.setFillColor(colors.HexColor('#d1d5db'))
    canvas_obj.rect(0, footer_y, width, footer_height, fill=True, stroke=False)
    
    # Green accent bar at top of footer
    canvas_obj.setFillColor(HEADER_GREEN)
    canvas_obj.rect(0, footer_y + footer_height, width, 4, fill=True, stroke=False)
    
    # Green decorative element at bottom-left corner
    # path = canvas_obj.beginPath()
    # path.moveTo(0, 0)
    # path.lineTo(0, 50)
    # path.curveTo(5, 35, 15, 20, 25, 15)
    # path.lineTo(30, 0)
    # path.close()
    # canvas_obj.drawPath(path, fill=True, stroke=False)
    
    # Footer text styling
    left_col_x = 55
    right_col_x = width / 2 + 20
    row1_y = footer_y + 38
    row2_y = footer_y + 18
    
    # FOOTER ICON ALIGNMENT: Perfectly align icon letters with parameter text baselines
    icon_radius = 8
    font_size = 11
    icon_font_size = 9
    # Circle center positioned to contain letter that's baseline-aligned with parameter text
    icon_circle_offset = round(icon_font_size / 2)  # Center circle on 9pt letter

    # Phone icon and number (row1_y is baseline for both)
    circle_cy = row1_y + icon_circle_offset
    canvas_obj.setFillColor(BLACK)
    canvas_obj.circle(left_col_x - 16, circle_cy, icon_radius, fill=True)
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica-Bold", icon_font_size)
    canvas_obj.drawCentredString(left_col_x - 16, row1_y, "C")  # Baseline aligned with text
    canvas_obj.setFillColor(BLACK)
    canvas_obj.setFont("Helvetica", font_size)
    canvas_obj.drawString(left_col_x, row1_y, COMPANY_PHONE)

    # Email icon and address (row2_y is baseline for both)
    circle_cy = row2_y + icon_circle_offset
    canvas_obj.setFillColor(BLACK)
    canvas_obj.circle(left_col_x - 16, circle_cy, icon_radius, fill=True)
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica-Bold", icon_font_size)
    canvas_obj.drawCentredString(left_col_x - 16, row2_y, "@")  # Baseline aligned with text
    canvas_obj.setFillColor(BLACK)
    canvas_obj.setFont("Helvetica", font_size)
    canvas_obj.drawString(left_col_x, row2_y, COMPANY_EMAIL)

    # Address icon and text (right column, row1_y for first address line)
    circle_cy = row1_y + icon_circle_offset
    canvas_obj.setFillColor(BLACK)
    canvas_obj.circle(right_col_x - 16, circle_cy, icon_radius, fill=True)
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica-Bold", icon_font_size)
    canvas_obj.drawCentredString(right_col_x - 16, row1_y, "O")  # Baseline aligned with text
    canvas_obj.setFillColor(BLACK)
    canvas_obj.setFont("Helvetica", font_size)
    # Address split over two lines
    canvas_obj.drawString(right_col_x, row1_y + 6, "Office 2nd Floor, Manogat Appt., Treasure Park")
    canvas_obj.drawString(right_col_x, row1_y - 6, "Road, Sahakar Nagar, Pune, Maharashtra 411009")

    # Website icon and URL (row2_y is baseline for both)
    circle_cy = row2_y + icon_circle_offset
    canvas_obj.setFillColor(BLACK)
    canvas_obj.circle(right_col_x - 16, circle_cy, icon_radius, fill=True)
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica-Bold", icon_font_size)
    canvas_obj.drawCentredString(right_col_x - 16, row2_y, "W")  # Baseline aligned with text
    canvas_obj.setFillColor(BLACK)
    canvas_obj.setFont("Helvetica", font_size)
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
    3. CTC = Total Gross + Employer PF + PT + Other Tax
    4. Monthly In-Hand = (Total Gross - PT - Other Tax - PF) / 12
    5. Employer PF is part of CTC, NEVER deducted from employee
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth
    
    buffer = io.BytesIO()
    width, height = A4
    
    # Define margins accounting for header/footer space
    left_margin = 50
    right_margin = 50
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
        spaceBefore=0,  # Consistent, control with Spacer
        spaceAfter=10
    )
    
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
    
    # Joining Documentation section
    elements.append(Spacer(1, 18))
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
    
    # Probation section
    elements.append(Spacer(1, 18))
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
    
    # Duties, Responsibilities section
    elements.append(Spacer(1, 18))
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
    elements.append(Spacer(1, 18))
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
    
    # Intellectual Property
    elements.append(Spacer(1, 18))
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
    elements.append(Spacer(1, 18))
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
    
    # Leave and WFH policies
    elements.append(Spacer(1, 18))
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
    elements.append(Spacer(1, 18))
    elements.append(Paragraph("<b>Miscellaneous:</b>", section_style))
    
    misc_items = [
        f"38. Notices: All employment-related notices shall be in writing and in English, delivered by hand, registered post, "
        f"email, courier, or speed post. You must update {COMPANY_NAME} of any address or contact detail changes.",
        "39. Severability: If any provision of this Letter is deemed invalid, the remaining provisions shall remain valid and enforceable.",
        f"40. Publicity: You cannot use {COMPANY_NAME}'s name or trademarks in a manner detrimental to {COMPANY_NAME}'s image "
        f"without prior written consent. Any articles mentioning {COMPANY_NAME} require {COMPANY_NAME}'s approval.",
        f"41. Non-Disparagement: You agree not to make false, defamatory, or disparaging statements about {COMPANY_NAME}, its employees, officers, or directors.",
        "42. Waiver: No delay or failure in exercising any rights shall be a waiver. Any waiver must be in writing and signed by an authorized representative.",
        "43. Integration: This Letter and its Exhibit constitute the entire agreement, superseding all previous agreements between the Parties.",
        f"44. Rights to Injunctive Relief: You acknowledge that breaching your obligations under this Agreement or {COMPANY_NAME}'s policies could cause significant, "
        f"ongoing harm. Therefore, {COMPANY_NAME} may seek injunctive relief in a court of appropriate jurisdiction."
    ]
    for item in misc_items:
        elements.append(Paragraph(item, list_style))
    
    # Jurisdiction
    elements.append(Spacer(1, 18))
    elements.append(Paragraph("<b>Jurisdiction:</b>", section_style))
    
    jurisdiction_items = [
        "45. If any term or provision of this appointment letter or any application thereof is declared or held invalid, illegal, or unenforceable, "
        "in whole or in part, whether generally or in any particular jurisdiction, such provision shall be deemed amended to the extent necessary to cure "
        "such invalidity, illegality, or unenforceability. The validity, legality, or enforceability of the remaining provisions, both generally and in "
        "every other jurisdiction, shall not be affected or impaired thereby.",
        "46. Courts of Mumbai shall have exclusive jurisdiction over any disputes arising out of or in connection with this contract.",
        f"47. As a full-time employee of {COMPANY_NAME}, you shall not be an employee and/or contractor worker or freelance worker of any other Company. "
        f"If found so, you are subjected to legal actions against you by {COMPANY_NAME}."
    ]
    for item in jurisdiction_items:
        elements.append(Paragraph(item, list_style))
    
    # Page break for Salary Annexure
    elements.append(PageBreak())
    
    # ===== SALARY ANNEXURE PAGE =====
    # Add spacing between header and title
    elements.append(Spacer(1, 20))
    
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
    
    # STRICT RULE: CTC = Total Gross + Employer PF + PT + Other Tax
    ctc_annual = (
        total_gross_annual + employer_pf_annual + professional_tax_annual + other_deduction_annual
    )
    monthly_ctc = round(ctc_annual / 12, 2)
    
    # Employee deductions (Professional Tax + Other Tax + PF)
    total_deductions_annual = professional_tax_annual + other_deduction_annual + employer_pf_annual
    
    # STRICT RULE: Monthly In-Hand = (Total Gross - PT - Other Tax - PF) / 12
    monthly_in_hand = round((total_gross_annual - total_deductions_annual) / 12, 2)
    
    # Salary Components table
    col_widths = [2.8*inch, 1.5*inch, 1.5*inch]
    table_total_width = sum(col_widths)  # Total width: 5.8*inch
    
    # Employee info table - use same width as components table
    info_data = [
        ["Company Name:", COMPANY_NAME],
        ["Candidate Name:", f"{employee_name}"],
        ["Designation:", f"{designation}"],
        ["Location:", "Pune"],
    ]
    
    # Convert to Paragraphs for bold support
    info_table_data = []
    for row in info_data:
        info_table_data.append([
            Paragraph(row[0], ParagraphStyle('InfoLabel', fontName='Helvetica-Bold', fontSize=11)),
            Paragraph(row[1], ParagraphStyle('InfoValue', fontName='Helvetica', fontSize=11))
        ])
    
    info_table = Table(info_table_data, colWidths=[2*inch, table_total_width - 2*inch])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))
    
    # Salary Components table (col_widths already defined above)
    components_data = [
        ["A) Fixed Gross Salary", "Per Annum", "Per Month"],
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
        # Header font size 12pt
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        # Data rows 11pt
        ('FONTSIZE', (0, 1), (-1, -1), 11),
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
        ["B) Employee Contribution", "Per Annum", "Per Month"],
        ["Professional Tax Deduction", format_currency_int(professional_tax_annual), pt_monthly_note],
        ["Other", format_currency_int(other_deduction_annual), format_currency(round(other_deduction_annual / 12, 2))],
        ["PF", format_currency_int(employer_pf_annual), format_currency(round(employer_pf_annual / 12, 2))],
        ["Variable Pay", format_currency_int(variable_pay_annual), format_currency(round(variable_pay_annual / 12, 2))],
    ]
    
    deductions_table = Table(deductions_data, colWidths=col_widths)
    deductions_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Header font size 12pt
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        # Data rows 11pt
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
    ]))
    elements.append(deductions_table)
    elements.append(Spacer(1, 10))
    
    # CTC Summary table - STRICT RULES: Total Gross vs CTC
    # CTC = Total Gross + Employer PF + PT + Other Tax
    # Keep header row (Per Annum / Per Month) and present A/B/CTC rows
    employee_contribution_annual = professional_tax_annual + other_deduction_annual + employer_pf_annual
    ctc_data = [
        ["", "Per Annum", "Per Month"],
        ["A) Gross Salary", format_currency_int(total_gross_annual), format_currency(monthly_gross)],
        ["B) Employee Contribution", format_currency_int(employee_contribution_annual), format_currency(round(employee_contribution_annual / 12, 2))],
        ["Total Cost To Company (CTC):", format_currency_int(ctc_annual), format_currency(monthly_ctc)],
    ]
    
    ctc_table = Table(ctc_data, colWidths=col_widths)
    ctc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        # Header font size 12pt (empty label cell kept but header row size set)
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        # Data rows 11pt
        ('FONTSIZE', (0, 1), (-1, -1), 11),
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
