from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import timedelta
from app.db.database import get_db
from app.db.models.user import User
from app.core.otp_utils import generate_otp, verify_otp
from app.services.email_service import send_otp_email
from app.core.security import create_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/send-otp")
def send_otp(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    otp = generate_otp(email)
    send_otp_email(email, otp)
    return {"message": "OTP sent successfully"}

@router.post("/verify-otp")
def verify_user(email: str, otp: int, db: Session = Depends(get_db)):
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
        "joining_date": user.joining_date.isoformat() if user.joining_date else None
    }

