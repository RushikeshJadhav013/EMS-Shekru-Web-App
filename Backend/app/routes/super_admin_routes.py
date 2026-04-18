from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import timedelta
from pydantic import EmailStr
import logging
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
    get_super_admin_counts,
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
from app.db.models.company import Company
from app.db.models.company_branch import CompanyBranch
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
    get_user_by_phone,
    get_user_by_pan_card,
    get_user_by_aadhar_card,
    get_admin_counts,
    get_users_by_role_created_by_admin,
)

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])


def _ensure_not_targeting_self_super_admin(
    current: SuperAdmin, target_super_admin_id: int, action_phrase: str
) -> None:
    if current.super_admin_id == target_super_admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot {action_phrase} your own super admin account.",
        )


def _get_super_admin_by_email(db: Session, email: str, exclude_super_admin_id: int | None = None):
    if not email:
        return None
    query = db.query(SuperAdmin).filter(func.lower(SuperAdmin.email) == email.strip().lower())
    if exclude_super_admin_id is not None:
        query = query.filter(SuperAdmin.super_admin_id != exclude_super_admin_id)
    return query.first()


def _get_super_admin_by_contact(
    db: Session, contact_no: str, exclude_super_admin_id: int | None = None
):
    if not contact_no:
        return None
    query = db.query(SuperAdmin).filter(SuperAdmin.contact_no == contact_no.strip())
    if exclude_super_admin_id is not None:
        query = query.filter(SuperAdmin.super_admin_id != exclude_super_admin_id)
    return query.first()


def _get_company_by_contact(db: Session, contact_no: str):
    if not contact_no:
        return None
    return db.query(Company).filter(Company.contact_number == contact_no.strip()).first()


def _get_branch_by_contact(db: Session, contact_no: str):
    if not contact_no:
        return None
    return db.query(CompanyBranch).filter(CompanyBranch.contact_number == contact_no.strip()).first()

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
    normalized_email = super_admin.email.strip().lower()

    # Prevent duplicate email addresses in super_admins table
    existing_email = _get_super_admin_by_email(db, normalized_email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A super admin already uses this email address",
        )
    # Enforce global email uniqueness against users table
    if get_user_by_email(db, normalized_email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address is already used by a user/admin account",
        )
    # Prevent duplicate contact numbers in super_admins table
    existing_contact = _get_super_admin_by_contact(db, super_admin.contact_no)
    if existing_contact:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A super admin already uses this contact number",
        )
    # Enforce global phone uniqueness against users table
    if get_user_by_phone(db, super_admin.contact_no):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact number is already used by a user/admin account",
        )
    if _get_company_by_contact(db, super_admin.contact_no):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact number is already used by a company.",
        )
    if _get_branch_by_contact(db, super_admin.contact_no):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact number is already used by a company branch.",
        )

    return create_super_admin(db, super_admin, current_super_admin.super_admin_id)

@router.put("/update/{super_admin_id}", response_model=SuperAdminOut)
def update_super_admin_route(
    super_admin_id: int, 
    super_admin: SuperAdminUpdate, 
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Update a super admin - requires authentication"""
    _ensure_not_targeting_self_super_admin(current_super_admin, super_admin_id, "edit")
    if super_admin.email:
        normalized_email = super_admin.email.strip().lower()
        existing_email = _get_super_admin_by_email(
            db,
            normalized_email,
            exclude_super_admin_id=super_admin_id,
        )
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another super admin already uses this email address",
            )
        if get_user_by_email(db, normalized_email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email address is already used by a user/admin account",
            )
    if super_admin.contact_no:
        existing_contact = _get_super_admin_by_contact(
            db,
            super_admin.contact_no,
            exclude_super_admin_id=super_admin_id,
        )
        if existing_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another super admin already uses this contact number",
            )
        if get_user_by_phone(db, super_admin.contact_no):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact number is already used by a user/admin account",
            )
        if _get_company_by_contact(db, super_admin.contact_no):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact number is already used by a company.",
            )
        if _get_branch_by_contact(db, super_admin.contact_no):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact number is already used by a company branch.",
            )

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
    _ensure_not_targeting_self_super_admin(current_super_admin, super_admin_id, "delete")
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
    status_filter: bool | None = None,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """List all super admins - requires authentication"""
    return list_super_admins(db, status=status_filter)


@router.patch("/status/{super_admin_id}", response_model=SuperAdminOut)
def set_super_admin_status_route(
    super_admin_id: int,
    status: SuperAdminStatusUpdate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Enable/disable a super admin - requires authentication"""
    _ensure_not_targeting_self_super_admin(current_super_admin, super_admin_id, "change the status of")
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


@router.get("/dashboard/super-admin-counts")
def get_super_admin_counts_route(
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    """Get super admin counts (total, active, inactive) for super admin dashboard"""
    return get_super_admin_counts(db)


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
    # Email is already normalized (lowercase) by AdminCreate schema validator
    email = admin.email
    employee_id = admin.employee_id.strip()
    pan_card = admin.pan_card.strip().upper() if admin.pan_card else None
    aadhar_card = admin.aadhar_card.strip() if admin.aadhar_card else None

    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user already exists with this email address",
        )
    if _get_super_admin_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address is already used by a super admin",
        )

    if get_user_by_employee_id(db, employee_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user already exists with employee ID '{employee_id}'",
        )

    # Check for duplicate phone number
    if admin.phone and admin.phone.strip():
        existing_phone = get_user_by_phone(db, admin.phone.strip())
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already exists. Please enter a unique phone number.",
            )
        existing_super_admin_contact = _get_super_admin_by_contact(db, admin.phone.strip())
        if existing_super_admin_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a super admin.",
            )
        existing_company_contact = _get_company_by_contact(db, admin.phone.strip())
        if existing_company_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a company.",
            )
        existing_branch_contact = _get_branch_by_contact(db, admin.phone.strip())
        if existing_branch_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a company branch.",
            )

    # Check for duplicate PAN card
    if pan_card:
        duplicate_pan = get_user_by_pan_card(db, pan_card)
        if duplicate_pan:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="PAN Card already exists. Please enter a unique PAN Card number.",
            )

    # Check for duplicate Aadhar card
    if aadhar_card:
        duplicate_aadhar = get_user_by_aadhar_card(db, aadhar_card)
        if duplicate_aadhar:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Aadhar Card already exists. Please enter a unique Aadhar Card number.",
            )

    payload = admin.model_dump()
    payload["email"] = email
    payload["employee_id"] = employee_id
    payload["pan_card"] = pan_card
    payload["aadhar_card"] = aadhar_card

    db_admin = create_admin_user(db, AdminCreate(**payload), created_by=current_super_admin.super_admin_id)

    return db_admin


@router.get("/admins", response_model=List[UserOut])
def list_admin_users_route(
    status_filter: bool | None = None,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    return list_admin_users(db, status=status_filter)


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
        # Email is already normalized (lowercase) by AdminUpdate schema validator
        existing = get_user_by_email(db, admin_update.email)
        if existing and existing.user_id != admin_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another user already uses this email address",
            )
        existing_super_admin = _get_super_admin_by_email(db, admin_update.email)
        if existing_super_admin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email address is already used by a super admin",
            )

    if admin_update.employee_id:
        normalized_emp = admin_update.employee_id.strip()
        existing_emp = get_user_by_employee_id(db, normalized_emp)
        if existing_emp and existing_emp.user_id != admin_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another user already uses employee ID '{normalized_emp}'",
            )
        admin_update.employee_id = normalized_emp

    # Check for duplicate phone number (excluding current admin)
    if admin_update.phone and admin_update.phone.strip():
        existing_phone = get_user_by_phone(db, admin_update.phone.strip())
        if existing_phone and existing_phone.user_id != admin_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already exists. Please enter a unique phone number.",
            )
        existing_super_admin_contact = _get_super_admin_by_contact(db, admin_update.phone.strip())
        if existing_super_admin_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a super admin.",
            )
        existing_company_contact = _get_company_by_contact(db, admin_update.phone.strip())
        if existing_company_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a company.",
            )
        existing_branch_contact = _get_branch_by_contact(db, admin_update.phone.strip())
        if existing_branch_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a company branch.",
            )

    # Check for duplicate PAN card (excluding current admin)
    if admin_update.pan_card and admin_update.pan_card.strip():
        admin_update.pan_card = admin_update.pan_card.strip().upper()
        duplicate_pan = get_user_by_pan_card(db, admin_update.pan_card)
        if duplicate_pan and duplicate_pan.user_id != admin_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="PAN Card already exists. Please enter a unique PAN Card number.",
            )

    # Check for duplicate Aadhar card (excluding current admin)
    if admin_update.aadhar_card and admin_update.aadhar_card.strip():
        admin_update.aadhar_card = admin_update.aadhar_card.strip()
        duplicate_aadhar = get_user_by_aadhar_card(db, admin_update.aadhar_card)
        if duplicate_aadhar and duplicate_aadhar.user_id != admin_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Aadhar Card already exists. Please enter a unique Aadhar Card number.",
            )

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
    if not super_admin.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive. Please contact your administrator for assistance.")
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
    if not super_admin.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive. Please contact your administrator for assistance.")
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
