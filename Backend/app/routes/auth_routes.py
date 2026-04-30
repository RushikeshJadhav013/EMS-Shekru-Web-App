from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from app.db.database import SessionLocal, get_db
from app.db.models.user import User
from app.core.otp_utils import generate_otp, verify_otp, get_environment_info, get_otp_info
from app.services.email_service import send_otp_email, test_email_configuration
from app.core.security import create_token
from app.core.config import settings
import logging
from app.dependencies import get_current_user, require_roles
from app.enums import RoleEnum
from app.crud.branch_admin_assignment_crud import list_companies_for_admin
from app.db.models.company import Company
from app.db.models.company_branch import CompanyBranch
from app.db.models.branch_admin_assignment import BranchAdminAssignment
from app.db.models.company_admin_assignment import CompanyAdminAssignment
from app.schemas.company_schema import AccessibleCompanyOut
from app.schemas.company_branch_schema import AccessibleBranchOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/send-otp")
def send_otp(email: str):
    """Send OTP with environment-aware logic"""
    # Keep DB usage short; do not hold a pooled connection while SMTP sends email.
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # ✅ Check if user is active before sending OTP
        if not user.is_active:
            raise HTTPException(
                status_code=403, 
                detail="Account is inactive. Please contact your administrator for assistance."
            )
    
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
        "expires_in_seconds": settings.OTP_EXPIRY_SECONDS
    }

@router.post("/verify-otp")
def verify_user(email: str, otp: int, db: Session = Depends(get_db)):
    """Verify OTP with environment-aware logic"""
    if not verify_otp(email, otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # ✅ Check if user is active before allowing login
    if not user.is_active:
        raise HTTPException(
            status_code=403, 
            detail="Account is inactive. Please contact your administrator for assistance."
        )
    
    # ✅ Mark email as verified on successful OTP verification (for salary document access)
    if not user.is_email_verified:
        user.is_email_verified = True
        db.commit()
        db.refresh(user)
    
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
        "profile_photo": user.profile_photo,
        "environment": settings.ENVIRONMENT
    }


@router.get("/me/companies", response_model=list[AccessibleCompanyOut])
def list_my_accessible_companies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
):
    """
    List companies accessible to the currently authenticated ADMIN user.

    This is intended for frontend tenant selection before navigating to `/{company_slug}/...`.
    """
    companies = list_companies_for_admin(db=db, admin_user_id=int(current_user.user_id))
    return companies


@router.get("/me/companies/{company_slug}/branches")
def list_my_accessible_branches_for_company(
    company_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
):
    """
    For the logged-in ADMIN:
    - Verify they can access the company identified by `company_slug`
    - Return whether they have company-level access
    - Return the list of branches they are assigned to in that company

    Frontend usage: after selecting a company (by slug), call this to decide
    whether to prompt for `X-Branch-Id` or treat the admin as company-level.
    """
    slug_norm = (company_slug or "").strip().lower()
    if not slug_norm:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="company_slug is required")

    company: Company | None = (
        db.query(Company)
        .filter(Company.company_slug == slug_norm, Company.is_deleted == False)  # noqa: E712
        .first()
    )
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    admin_user_id = int(current_user.user_id)

    has_company_level_access = (
        db.query(CompanyAdminAssignment.assignment_id)
        .filter(
            CompanyAdminAssignment.admin_user_id == admin_user_id,
            CompanyAdminAssignment.company_id == int(company.company_id),
            CompanyAdminAssignment.is_active == True,  # noqa: E712
        )
        .first()
        is not None
    )

    # Branches assigned to this admin within the selected company
    branches = (
        db.query(CompanyBranch)
        .join(BranchAdminAssignment, BranchAdminAssignment.branch_id == CompanyBranch.branch_id)
        .filter(
            CompanyBranch.company_id == int(company.company_id),
            CompanyBranch.is_deleted == False,  # noqa: E712
            BranchAdminAssignment.admin_user_id == admin_user_id,
            BranchAdminAssignment.is_active == True,  # noqa: E712
        )
        .order_by(CompanyBranch.branch_name.asc())
        .all()
    )

    # Access is granted if admin has company-level access OR at least one branch assignment in this company.
    if not has_company_level_access and not branches:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied for this company")

    return {
        "company_id": int(company.company_id),
        "company_slug": company.company_slug,
        "company_name": company.company_name,
        "has_company_level_access": bool(has_company_level_access),
        "branches": [AccessibleBranchOut.model_validate(b).model_dump() for b in branches],
    }

# Development/Testing endpoints for debugging OTP
@router.get("/debug/environment", include_in_schema=False)
def get_debug_environment_info():
    """Get environment information (only in non-production)"""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not available in production")
    
    return get_environment_info()

@router.get("/debug/otp/{email}", include_in_schema=False)
def get_debug_otp_info(email: str):
    """Get OTP information for debugging (only in non-production)"""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not available in production")
    
    return get_otp_info(email)

@router.post("/debug/test-email", include_in_schema=False)
def test_email_service():
    """Test email service configuration (only in non-production)"""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not available in production")
    
    return test_email_configuration()

@router.post("/debug/clear-otps", include_in_schema=False)
def clear_all_otps_debug():
    """Clear all OTPs (only in non-production)"""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not available in production")
    
    from app.core.otp_utils import clear_all_otps
    clear_all_otps()
    return {"message": "All OTPs cleared"}

