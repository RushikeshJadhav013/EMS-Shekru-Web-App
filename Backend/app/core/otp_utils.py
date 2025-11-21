import random
from datetime import datetime, timedelta
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

OTP_STORE = {}

def generate_otp(email: str) -> int:
    """Generate OTP based on environment settings"""
    if settings.should_use_fixed_otp:
        # Use fixed OTP for development and testing
        otp = int(settings.TESTING_OTP)
        logger.info(f"Using fixed OTP {otp} for email {email} in {settings.ENVIRONMENT} environment")
    else:
        # Generate random OTP for production
        otp = random.randint(100000, 999999)
        logger.info(f"Generated random OTP {otp} for email {email} in {settings.ENVIRONMENT} environment")
    
    OTP_STORE[email] = {
        "otp": otp, 
        "expiry": datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
        "environment": settings.ENVIRONMENT
    }
    return otp

def verify_otp(email: str, otp: int) -> bool:
    """Verify OTP with environment-aware logic"""
    record = OTP_STORE.get(email)
    
    if not record:
        logger.warning(f"No OTP record found for email {email}")
        return False
    
    # In testing/development, allow the testing OTP even if different from stored
    if settings.should_use_fixed_otp and otp == int(settings.TESTING_OTP):
        logger.info(f"Accepted testing OTP {otp} for email {email} in {settings.ENVIRONMENT}")
        del OTP_STORE[email]
        return True
    
    # Verify the actual stored OTP
    if record["otp"] != otp:
        logger.warning(f"Invalid OTP {otp} for email {email}. Expected {record['otp']}")
        return False
    
    # Check expiry
    if datetime.utcnow() > record["expiry"]:
        logger.warning(f"OTP expired for email {email}")
        del OTP_STORE[email]
        return False
    
    logger.info(f"OTP verified successfully for email {email} in {settings.ENVIRONMENT}")
    del OTP_STORE[email]
    return True

def get_otp_info(email: str) -> dict:
    """Get OTP information for debugging (only in non-production)"""
    if settings.is_production:
        return {"error": "OTP info not available in production"}
    
    record = OTP_STORE.get(email)
    if not record:
        return {"error": "No OTP found"}
    
    return {
        "email": email,
        "otp": record["otp"],
        "expiry": record["expiry"].isoformat(),
        "environment": record["environment"],
        "is_expired": datetime.utcnow() > record["expiry"],
        "time_remaining": max(0, (record["expiry"] - datetime.utcnow()).total_seconds())
    }

def clear_all_otps():
    """Clear all OTPs (useful for testing)"""
    global OTP_STORE
    OTP_STORE.clear()
    logger.info("All OTPs cleared")

def get_environment_info() -> dict:
    """Get current environment information for debugging"""
    return {
        "environment": settings.ENVIRONMENT,
        "should_use_fixed_otp": settings.should_use_fixed_otp,
        "should_send_email": settings.should_send_email,
        "testing_otp": settings.TESTING_OTP if settings.should_use_fixed_otp else None,
        "enable_email_otp": settings.ENABLE_EMAIL_OTP,
        "active_otps": len(OTP_STORE)
    }
