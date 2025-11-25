import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def send_otp_email(email: str, otp: int, environment_info: dict = None):
    """Send OTP email based on environment settings"""
    
    if not settings.should_send_email:
        # For development/testing, just log the OTP
        logger.info(f"🔧 [{settings.ENVIRONMENT.upper()}] OTP for {email}: {otp}")
        print(f"\n🔧 [{settings.ENVIRONMENT.upper()}] LOGIN OTP")
        print(f"📧 Email: {email}")
        print(f"🔢 OTP: {otp}")
        print(f"⏰ Valid for: {settings.OTP_EXPIRY_MINUTES} minutes")
        print(f"🌍 Environment: {settings.ENVIRONMENT}")
        if environment_info:
            print(f"ℹ️  Environment Info: {environment_info}")
        print("=" * 50)
        return True
    
    # For production, send actual email
    if not all([settings.SMTP_HOST, settings.SMTP_USERNAME, settings.SMTP_PASSWORD, settings.SMTP_FROM_EMAIL]):
        logger.error("SMTP settings not configured for production environment")
        return False
    
    try:
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_FROM_EMAIL
        msg['To'] = email
        msg['Subject'] = f"Your Login OTP - {settings.PROJECT_NAME}"
        
        # Email body
        body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Your Login OTP</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4F46E5; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9f9f9; }}
                .otp {{ font-size: 32px; font-weight: bold; color: #4F46E5; text-align: center; padding: 20px; background: white; border-radius: 8px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .warning {{ color: #dc2626; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{settings.PROJECT_NAME}</h1>
                    <p>One-Time Password (OTP)</p>
                </div>
                <div class="content">
                    <h2>Your Login OTP</h2>
                    <p>Use the following OTP to complete your login process:</p>
                    <div class="otp">{otp}</div>
                    <p><strong>Important:</strong></p>
                    <ul>
                        <li>This OTP is valid for <strong>{settings.OTP_EXPIRY_MINUTES} minutes</strong></li>
                        <li>Never share this OTP with anyone</li>
                        <li class="warning">If you didn't request this OTP, please contact support immediately</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>This is an automated message from {settings.PROJECT_NAME}</p>
                    <p>Environment: {settings.ENVIRONMENT}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"OTP email sent successfully to {email} in {settings.ENVIRONMENT} environment")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {str(e)}")
        return False

def test_email_configuration():
    """Test email configuration (for development/testing)"""
    if settings.is_production:
        return {"error": "Email testing not allowed in production"}
    
    if not settings.should_send_email:
        return {"message": "Email sending is disabled in current environment"}
    
    try:
        test_email = settings.SMTP_FROM_EMAIL
        test_otp = 123456
        
        result = send_otp_email(test_email, test_otp)
        
        if result:
            return {"success": True, "message": f"Test email sent to {test_email}"}
        else:
            return {"success": False, "message": "Failed to send test email"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

