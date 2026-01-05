"""
Salary Email Service - Send salary slips and increment letters via email
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from app.core.config import settings
import logging
import io
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Company configuration
try:
    from app.config.company_config import COMPANY_NAME
except ImportError:
    COMPANY_NAME = "Shekru Labs India Pvt Ltd"


def send_salary_slip_email(
    to_email: str,
    employee_name: str,
    month: int,
    year: int,
    pdf_buffer: io.BytesIO,
    net_salary: float
) -> bool:
    """
    Send salary slip PDF via email
    
    Args:
        to_email: Employee email address
        employee_name: Employee name
        month: Salary month (1-12)
        year: Salary year
        pdf_buffer: PDF file buffer
        net_salary: Net payable amount
    
    Returns:
        bool: True if email sent successfully
    """
    if not settings.should_send_email:
        logger.info(f"[{settings.ENVIRONMENT.upper()}] Salary slip email would be sent to {to_email}")
        print(f"\n📧 [{settings.ENVIRONMENT.upper()}] SALARY SLIP EMAIL")
        print(f"To: {to_email}")
        print(f"Employee: {employee_name}")
        print(f"Period: {_get_month_name(month)} {year}")
        print(f"Net Salary: ₹{net_salary:,.2f}")
        print("=" * 50)
        return True
    
    if not _validate_smtp_config():
        logger.error("SMTP settings not configured")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = f"Salary Slip - {_get_month_name(month)} {year} | {COMPANY_NAME}"
        
        # Email body
        body = _create_salary_slip_email_body(employee_name, month, year, net_salary)
        msg.attach(MIMEText(body, 'html'))
        
        # Attach PDF
        pdf_buffer.seek(0)
        pdf_attachment = MIMEApplication(pdf_buffer.read(), _subtype='pdf')
        filename = f"Salary_Slip_{_get_month_name(month)}_{year}_{employee_name.replace(' ', '_')}.pdf"
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(pdf_attachment)
        
        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Salary slip email sent to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send salary slip email to {to_email}: {str(e)}")
        return False


def send_increment_letter_email(
    to_email: str,
    employee_name: str,
    previous_salary: float,
    new_salary: float,
    increment_amount: float,
    effective_date: datetime,
    pdf_buffer: io.BytesIO
) -> bool:
    """
    Send increment letter PDF via email
    
    Args:
        to_email: Employee email address
        employee_name: Employee name
        previous_salary: Previous monthly salary
        new_salary: New monthly salary
        increment_amount: Increment amount
        effective_date: Effective date of increment
        pdf_buffer: PDF file buffer
    
    Returns:
        bool: True if email sent successfully
    """
    if not settings.should_send_email:
        logger.info(f"[{settings.ENVIRONMENT.upper()}] Increment letter email would be sent to {to_email}")
        print(f"\n📧 [{settings.ENVIRONMENT.upper()}] INCREMENT LETTER EMAIL")
        print(f"To: {to_email}")
        print(f"Employee: {employee_name}")
        print(f"Previous Salary: ₹{previous_salary:,.2f}")
        print(f"New Salary: ₹{new_salary:,.2f}")
        print(f"Increment: ₹{increment_amount:,.2f}")
        print(f"Effective Date: {effective_date.strftime('%d %B %Y')}")
        print("=" * 50)
        return True
    
    if not _validate_smtp_config():
        logger.error("SMTP settings not configured")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = f"Letter of Increment - {COMPANY_NAME}"
        
        # Email body
        body = _create_increment_letter_email_body(
            employee_name, previous_salary, new_salary, 
            increment_amount, effective_date
        )
        msg.attach(MIMEText(body, 'html'))
        
        # Attach PDF
        pdf_buffer.seek(0)
        pdf_attachment = MIMEApplication(pdf_buffer.read(), _subtype='pdf')
        filename = f"Increment_Letter_{employee_name.replace(' ', '_')}.pdf"
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(pdf_attachment)
        
        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Increment letter email sent to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send increment letter email to {to_email}: {str(e)}")
        return False


def send_salary_annexure_email(
    to_email: str,
    employee_name: str,
    designation: str,
    ctc_annual: float,
    pdf_buffer: io.BytesIO
) -> bool:
    """
    Send salary annexure/offer letter PDF via email
    """
    if not settings.should_send_email:
        logger.info(f"[{settings.ENVIRONMENT.upper()}] Salary annexure email would be sent to {to_email}")
        print(f"\n📧 [{settings.ENVIRONMENT.upper()}] SALARY ANNEXURE EMAIL")
        print(f"To: {to_email}")
        print(f"Employee: {employee_name}")
        print(f"Designation: {designation}")
        print(f"Annual CTC: ₹{ctc_annual:,.2f}")
        print("=" * 50)
        return True
    
    if not _validate_smtp_config():
        logger.error("SMTP settings not configured")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = f"Salary Annexure - {COMPANY_NAME}"
        
        # Email body
        body = _create_salary_annexure_email_body(employee_name, designation, ctc_annual)
        msg.attach(MIMEText(body, 'html'))
        
        # Attach PDF
        pdf_buffer.seek(0)
        pdf_attachment = MIMEApplication(pdf_buffer.read(), _subtype='pdf')
        filename = f"Salary_Annexure_{employee_name.replace(' ', '_')}.pdf"
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(pdf_attachment)
        
        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Salary annexure email sent to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send salary annexure email to {to_email}: {str(e)}")
        return False


# ==================== HELPER FUNCTIONS ====================

def _validate_smtp_config() -> bool:
    """Validate SMTP configuration"""
    return all([
        settings.SMTP_HOST,
        settings.SMTP_USERNAME,
        settings.SMTP_PASSWORD,
        settings.SMTP_FROM_EMAIL
    ])


def _get_month_name(month: int) -> str:
    """Get month name from number"""
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    return months[month - 1] if 1 <= month <= 12 else ""


def _create_salary_slip_email_body(
    employee_name: str, 
    month: int, 
    year: int, 
    net_salary: float
) -> str:
    """Create HTML email body for salary slip"""
    month_name = _get_month_name(month)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Salary Slip</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background: #f9f9f9; }}
            .highlight {{ font-size: 24px; font-weight: bold; color: #4CAF50; text-align: center; padding: 15px; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{COMPANY_NAME}</h1>
                <p>Salary Slip - {month_name} {year}</p>
            </div>
            <div class="content">
                <h2>Dear {employee_name},</h2>
                <p>Please find attached your salary slip for the month of <strong>{month_name} {year}</strong>.</p>
                <div class="highlight">
                    Net Payable: ₹{net_salary:,.2f}
                </div>
                <p>If you have any queries regarding your salary, please contact the HR department.</p>
                <p>Best regards,<br>HR Department<br>{COMPANY_NAME}</p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply directly to this email.</p>
                <p>© {datetime.now().year} {COMPANY_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """


def _create_increment_letter_email_body(
    employee_name: str,
    previous_salary: float,
    new_salary: float,
    increment_amount: float,
    effective_date: datetime
) -> str:
    """Create HTML email body for increment letter"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Letter of Increment</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background: #f9f9f9; }}
            .highlight {{ background: #e8f5e9; padding: 15px; border-radius: 8px; margin: 15px 0; }}
            .salary-info {{ display: flex; justify-content: space-between; margin: 10px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{COMPANY_NAME}</h1>
                <p>Letter of Increment</p>
            </div>
            <div class="content">
                <h2>Dear {employee_name},</h2>
                <p>Congratulations! We are pleased to inform you about your salary revision.</p>
                <div class="highlight">
                    <p><strong>Previous Salary:</strong> ₹{previous_salary:,.2f}</p>
                    <p><strong>Increment:</strong> ₹{increment_amount:,.2f}</p>
                    <p><strong>New Salary:</strong> ₹{new_salary:,.2f}</p>
                    <p><strong>Effective Date:</strong> {effective_date.strftime('%d %B %Y')}</p>
                </div>
                <p>Please find the detailed increment letter attached to this email.</p>
                <p>We appreciate your contributions and look forward to your continued success.</p>
                <p>Best regards,<br>HR Department<br>{COMPANY_NAME}</p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply directly to this email.</p>
                <p>© {datetime.now().year} {COMPANY_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """


def _create_salary_annexure_email_body(
    employee_name: str,
    designation: str,
    ctc_annual: float
) -> str:
    """Create HTML email body for salary annexure"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Salary Annexure</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background: #f9f9f9; }}
            .highlight {{ background: #e8f5e9; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{COMPANY_NAME}</h1>
                <p>Salary Annexure</p>
            </div>
            <div class="content">
                <h2>Dear {employee_name},</h2>
                <p>Please find attached your salary annexure document with complete compensation details.</p>
                <div class="highlight">
                    <p><strong>Designation:</strong> {designation}</p>
                    <p><strong>Annual CTC:</strong> ₹{ctc_annual:,.2f}</p>
                </div>
                <p>This document contains the detailed breakdown of your salary components.</p>
                <p>If you have any queries, please contact the HR department.</p>
                <p>Best regards,<br>HR Department<br>{COMPANY_NAME}</p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply directly to this email.</p>
                <p>© {datetime.now().year} {COMPANY_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
