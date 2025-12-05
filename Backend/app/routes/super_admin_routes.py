from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import timedelta
from pydantic import EmailStr
from app.db.database import get_db
from app.crud.super_admin_crud import (
    # get_total_companies,
    # get_total_owners,
    # get_company_employee_counts,
    create_super_admin,
    update_super_admin,
    delete_super_admin,
    get_super_admin,
    list_super_admins
)
from app.schemas.super_admin_schema import SuperAdminCreate, SuperAdminUpdate, SuperAdminOut
from app.db.models.super_admin import SuperAdmin
from app.core.security import create_token
from app.core.otp_utils import generate_otp, verify_otp, get_environment_info
from app.services.email_service import send_otp_email
from app.core.config import settings
from app.dependencies import get_current_super_admin
from typing import List

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])

# @router.get("/total-companies")
# def total_companies(db: Session = Depends(get_db)):
#     try:
#         return {"total_companies": get_total_companies(db)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/total-owners")
# def total_owners(db: Session = Depends(get_db)):
#     try:
#         return {"total_owners": get_total_owners(db)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/company-employee-counts")
# def company_employee_counts(db: Session = Depends(get_db)):
#     try:
#         return get_company_employee_counts(db)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@router.post("/create", response_model=SuperAdminOut)
def create_super_admin_route(
    super_admin: SuperAdminCreate, 
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Create a new super admin - requires authentication"""
    return create_super_admin(db, super_admin, current_super_admin.super_admin_id)

@router.put("/update/{super_admin_id}", response_model=SuperAdminOut)
def update_super_admin_route(
    super_admin_id: int, 
    super_admin: SuperAdminUpdate, 
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Update a super admin - requires authentication"""
    updated_admin = update_super_admin(db, super_admin_id, super_admin, current_super_admin.super_admin_id)
    if not updated_admin:
        raise HTTPException(status_code=404, detail="Super Admin not found")
    return updated_admin

@router.delete("/delete/{super_admin_id}")
def delete_super_admin_route(
    super_admin_id: int, 
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Delete a super admin - requires authentication"""
    deleted_admin = delete_super_admin(db, super_admin_id)
    if not deleted_admin:
        raise HTTPException(status_code=404, detail="Super Admin not found")
    return {"detail": "Super Admin deleted"}

@router.get("/view/{super_admin_id}", response_model=SuperAdminOut)
def get_super_admin_route(
    super_admin_id: int, 
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """View a super admin - requires authentication"""
    super_admin = get_super_admin(db, super_admin_id)
    if not super_admin:
        raise HTTPException(status_code=404, detail="Super Admin not found")
    return super_admin

@router.get("/list", response_model=List[SuperAdminOut])
def list_super_admins_route(
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """List all super admins - requires authentication"""
    return list_super_admins(db)

@router.post("/send-otp")
def send_otp_super_admin(email: EmailStr, db: Session = Depends(get_db)):
    """Send OTP to super admin email"""
    super_admin = db.query(SuperAdmin).filter(SuperAdmin.email == email).first()
    if not super_admin:
        raise HTTPException(status_code=404, detail="Super Admin not found")
    
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
def verify_otp_super_admin(email: EmailStr, otp: int, db: Session = Depends(get_db)):
    """Verify OTP and return JWT token for super admin"""
    super_admin = db.query(SuperAdmin).filter(SuperAdmin.email == email).first()
    if not super_admin:
        raise HTTPException(status_code=404, detail="Super Admin not found")

    if not verify_otp(email, otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    token = create_token({"sub": super_admin.email, "role": "super_admin"}, timedelta(hours=2))
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "super_admin",
        "super_admin_id": super_admin.super_admin_id,
        "email": super_admin.email,
        "name": super_admin.name,
        "environment": settings.ENVIRONMENT
    }
