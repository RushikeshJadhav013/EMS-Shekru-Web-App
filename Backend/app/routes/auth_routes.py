from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import timedelta
from app.db.database import get_db
from app.db.models.user import User
from app.core.otp_utils import generate_otp, verify_otp, get_environment_info, get_otp_info
from app.services.email_service import send_otp_email, test_email_configuration
from app.core.security import create_token
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/send-otp")
def send_otp(email: str, db: Session = Depends(get_db)):
    """Send OTP with environment-aware logic"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate OTP based on environment
    otp = generate_otp(email)
    
    # Get environment info for logging
    env_info = get_environment_info()
    
    # Send OTP using environment-aware email service
    email_sent = send_otp_email(email, otp, env_info)
    
    response_message = "OTP sent successfully"
    if not settings.should_send_email:
        response_message = f"OTP generated (check console for {settings.ENVIRONMENT} environment)"
    
    return {
        "message": response_message,
        "environment": settings.ENVIRONMENT,
        "otp_method": "email" if settings.should_send_email else "console",
        "expires_in_minutes": settings.OTP_EXPIRY_MINUTES
    }

@router.post("/verify-otp")
def verify_user(email: str, otp: int, db: Session = Depends(get_db)):
    """Verify OTP with environment-aware logic"""
    if not verify_otp(email, otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Convert role enum to string value
    role_value = user.role.value if hasattr(user.role, 'value') else str(user.role)
    
    token = create_token({"sub": user.email, "role": role_value}, timedelta(hours=2))
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role_value,
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
        "department": user.department,
        "designation": user.designation,
        "joining_date": user.joining_date.isoformat() if user.joining_date else None,
        "environment": settings.ENVIRONMENT
    }

# Development/Testing endpoints for debugging OTP
@router.get("/debug/environment")
def get_debug_environment_info():
    """Get environment information (only in non-production)"""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not available in production")
    
    return get_environment_info()

@router.get("/debug/otp/{email}")
def get_debug_otp_info(email: str):
    """Get OTP information for debugging (only in non-production)"""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not available in production")
    
    return get_otp_info(email)

@router.post("/debug/test-email")
def test_email_service():
    """Test email service configuration (only in non-production)"""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not available in production")
    
    return test_email_configuration()

@router.post("/debug/clear-otps")
def clear_all_otps_debug():
    """Clear all OTPs (only in non-production)"""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not available in production")
    
    from app.core.otp_utils import clear_all_otps
    clear_all_otps()
    return {"message": "All OTPs cleared"}

