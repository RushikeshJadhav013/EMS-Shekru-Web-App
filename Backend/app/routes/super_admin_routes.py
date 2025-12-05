from fastapi import APIRouter, Depends, HTTPException, status
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
    list_super_admins,
    set_super_admin_status,
)
from app.schemas.super_admin_schema import (
    SuperAdminCreate,
    SuperAdminUpdate,
    SuperAdminOut,
    SuperAdminStatusUpdate,
)
from app.schemas.user_schema import (
    UserOut,
    UpdateStatusSchema,
    AdminCreate,
    AdminUpdate,
)
from app.db.models.super_admin import SuperAdmin
from app.core.security import create_token
from app.core.otp_utils import generate_otp, verify_otp, get_environment_info
from app.services.email_service import send_otp_email
from app.core.config import settings
from app.dependencies import get_current_super_admin
from typing import List
from app.crud.user_crud import (
    create_admin_user,
    list_admin_users,
    get_admin_user,
    update_admin_user,
    set_admin_status,
    delete_admin_user,
    get_user_by_email,
    get_user_by_employee_id,
    get_admin_counts,
    get_users_by_role_created_by_admin,
)

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


@router.patch("/status/{super_admin_id}", response_model=SuperAdminOut)
def set_super_admin_status_route(
    super_admin_id: int,
    status: SuperAdminStatusUpdate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Enable/disable a super admin - requires authentication"""
    updated_admin = set_super_admin_status(
        db,
        super_admin_id,
        status.is_active,
        current_super_admin.super_admin_id,
    )
    if not updated_admin:
        raise HTTPException(status_code=404, detail="Super Admin not found")
    return updated_admin


# --------------------------
# Super Admin Dashboard
# --------------------------
@router.get("/dashboard/admin-counts")
def get_admin_counts_route(
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    """Get admin counts (total, active, inactive) for super admin dashboard"""
    return get_admin_counts(db)


@router.get("/dashboard/users-by-role-created-by-admin")
def get_users_by_role_created_by_admin_route(
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    """Get counts of users by role where users were created by admins (total, active, inactive, resigned)"""
    return get_users_by_role_created_by_admin(db)


# --------------------------
# Admin management (users table) – Super Admin only
# --------------------------
@router.post("/admins", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_admin_user_route(
    admin: AdminCreate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    email = admin.email.strip()
    employee_id = admin.employee_id.strip()
    pan_card = admin.pan_card.strip().upper() if admin.pan_card else None
    aadhar_card = admin.aadhar_card.strip() if admin.aadhar_card else None

    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user already exists with this email address",
        )

    if get_user_by_employee_id(db, employee_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user already exists with employee ID '{employee_id}'",
        )

    payload = admin.model_dump()
    payload["email"] = email
    payload["employee_id"] = employee_id
    payload["pan_card"] = pan_card
    payload["aadhar_card"] = aadhar_card

    return create_admin_user(db, AdminCreate(**payload), created_by=current_super_admin.super_admin_id)


@router.get("/admins", response_model=List[UserOut])
def list_admin_users_route(
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    return list_admin_users(db)


@router.get("/admins/{admin_id}", response_model=UserOut)
def get_admin_user_route(
    admin_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    admin = get_admin_user(db, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    return admin


@router.put("/admins/{admin_id}", response_model=UserOut)
def update_admin_user_route(
    admin_id: int,
    admin_update: AdminUpdate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    if admin_update.email:
        normalized_email = admin_update.email.strip()
        existing = get_user_by_email(db, normalized_email)
        if existing and existing.user_id != admin_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another user already uses this email address",
            )
        admin_update.email = normalized_email

    if admin_update.employee_id:
        normalized_emp = admin_update.employee_id.strip()
        existing_emp = get_user_by_employee_id(db, normalized_emp)
        if existing_emp and existing_emp.user_id != admin_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another user already uses employee ID '{normalized_emp}'",
            )
        admin_update.employee_id = normalized_emp

    if admin_update.pan_card:
        admin_update.pan_card = admin_update.pan_card.strip().upper()

    if admin_update.aadhar_card:
        admin_update.aadhar_card = admin_update.aadhar_card.strip()

    updated = update_admin_user(db, admin_id, admin_update, updated_by=current_super_admin.super_admin_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Admin not found")
    return updated


@router.patch("/admins/{admin_id}/status", response_model=UserOut)
def set_admin_user_status_route(
    admin_id: int,
    status: UpdateStatusSchema,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    updated = set_admin_status(db, admin_id, status.is_active, updated_by=current_super_admin.super_admin_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Admin not found")
    return updated


@router.delete("/admins/{admin_id}")
def delete_admin_user_route(
    admin_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    deleted = delete_admin_user(db, admin_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Admin not found")
    return {"detail": "Admin deleted successfully"}

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
