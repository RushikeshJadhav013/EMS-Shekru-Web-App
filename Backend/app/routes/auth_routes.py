from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from app.db.database import SessionLocal, get_db
from app.db.models.user import User
from app.core.otp_utils import generate_otp, verify_otp, get_environment_info, get_otp_info
from app.core.pin_utils import (
    verify_login_pin,
    is_user_pin_locked,
    get_pin_lock_remaining_seconds,
    get_pin_environment_info,
    validate_pin_for_set,
)
from app.services.email_service import send_otp_email, test_email_configuration
from app.core.security import create_token
from app.core.config import settings
import logging
from app.dependencies import get_current_user, require_roles
from app.enums import RoleEnum
from app.crud.branch_admin_assignment_crud import list_companies_for_admin
from app.crud.user_crud import (
    get_user_by_email,
    set_user_pin,
    clear_user_pin,
    record_pin_failure,
    reset_pin_attempts,
)
from app.db.models.company import Company
from app.db.models.company_branch import CompanyBranch
from app.db.models.branch_admin_assignment import BranchAdminAssignment
from app.db.models.company_admin_assignment import CompanyAdminAssignment
from app.schemas.company_schema import AccessibleCompanyOut
from app.schemas.company_branch_schema import AccessibleBranchOut
from app.schemas.auth_schema import (
    LoginPinRequest,
    SetPinRequest,
    ChangePinRequest,
    ResetPinRequest,
    LoginOptionsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _role_value(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def _get_active_user_by_email(db: Session, email: str) -> User:
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is inactive. Please contact your administrator for assistance.",
        )
    return user


def _issue_user_login_response(user: User, db: Session) -> dict:
    if not user.is_email_verified:
        user.is_email_verified = True
        db.commit()
        db.refresh(user)

    role_value = _role_value(user)
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
        "is_pin_set": bool(user.is_pin_set),
        "requires_pin_setup": not bool(user.is_pin_set),
        "environment": settings.ENVIRONMENT,
    }


def _login_options_for_user(user: User) -> LoginOptionsResponse:
    has_pin = bool(user.is_pin_set)
    pin_locked = is_user_pin_locked(user)
    methods = ["otp"]
    if has_pin and not pin_locked:
        methods.insert(0, "pin")

    return LoginOptionsResponse(
        email=user.email,
        role=_role_value(user),
        has_pin=has_pin,
        pin_locked=pin_locked,
        pin_locked_until=user.pin_locked_until if pin_locked else None,
        available_methods=methods,
        requires_pin_setup=not has_pin,
    )


@router.get("/login-options", response_model=LoginOptionsResponse)
def get_login_options(email: str, db: Session = Depends(get_db)):
    """Return available login methods for a user email."""
    user = _get_active_user_by_email(db, email)
    return _login_options_for_user(user)


@router.post("/login-pin")
def login_with_pin(payload: LoginPinRequest, db: Session = Depends(get_db)):
    """Login with email and 4-digit PIN."""
    user = _get_active_user_by_email(db, payload.email)

    if is_user_pin_locked(user):
        remaining = get_pin_lock_remaining_seconds(user)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "message": "PIN is temporarily locked due to too many failed attempts.",
                "retry_after_seconds": remaining,
                "pin_locked_until": user.pin_locked_until.isoformat() if user.pin_locked_until else None,
            },
        )

    if not verify_login_pin(user, payload.pin):
        user = record_pin_failure(db, user)
        attempts_remaining = max(0, settings.PIN_MAX_ATTEMPTS - int(user.pin_failed_attempts or 0))
        if is_user_pin_locked(user):
            remaining = get_pin_lock_remaining_seconds(user)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "message": "PIN is temporarily locked due to too many failed attempts.",
                    "retry_after_seconds": remaining,
                    "pin_locked_until": user.pin_locked_until.isoformat() if user.pin_locked_until else None,
                },
            )
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid PIN",
                "attempts_remaining": attempts_remaining,
            },
        )

    user = reset_pin_attempts(db, user)
    return _issue_user_login_response(user, db)


@router.post("/set-pin")
def set_pin(
    payload: SetPinRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a 4-digit PIN after OTP login (first-time setup)."""
    if current_user.is_pin_set:
        raise HTTPException(
            status_code=400,
            detail="PIN is already set. Use change-pin to update it.",
        )

    pin = validate_pin_for_set(payload.pin)
    user = db.query(User).filter(User.user_id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    set_user_pin(db, user, pin)
    return {
        "message": "PIN set successfully",
        "is_pin_set": True,
        "requires_pin_setup": False,
    }


@router.post("/change-pin")
def change_pin(
    payload: ChangePinRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change PIN while logged in."""
    user = db.query(User).filter(User.user_id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_pin_set:
        raise HTTPException(status_code=400, detail="PIN is not set. Use set-pin first.")

    if is_user_pin_locked(user):
        remaining = get_pin_lock_remaining_seconds(user)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "message": "PIN is temporarily locked due to too many failed attempts.",
                "retry_after_seconds": remaining,
            },
        )

    if not verify_login_pin(user, payload.current_pin):
        user = record_pin_failure(db, user)
        raise HTTPException(status_code=400, detail="Current PIN is incorrect")

    new_pin = validate_pin_for_set(payload.new_pin)
    set_user_pin(db, user, new_pin)
    return {"message": "PIN changed successfully", "is_pin_set": True}


@router.post("/reset-pin")
def reset_pin(payload: ResetPinRequest, db: Session = Depends(get_db)):
    """Reset PIN using email OTP verification."""
    user = _get_active_user_by_email(db, payload.email)
    if not verify_otp(payload.email, payload.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    pin = validate_pin_for_set(payload.new_pin)
    set_user_pin(db, user, pin)
    return {
        "message": "PIN reset successfully",
        "is_pin_set": True,
        "requires_pin_setup": False,
    }


@router.post("/send-otp")
def send_otp(email: str):
    """Send OTP with environment-aware logic"""
    # Keep DB usage short; do not hold a pooled connection while SMTP sends email.
    with SessionLocal() as db:
        _get_active_user_by_email(db, email)

    # Generate OTP based on environment
    otp = generate_otp(email)

    # Get environment info for logging
    env_info = get_environment_info()

    # Send OTP using environment-aware email service
    send_otp_email(email, otp, env_info)

    response_message = "OTP sent successfully"
    if not settings.should_send_email:
        response_message = f"OTP generated (check console for {settings.ENVIRONMENT} environment)"

    return {
        "message": response_message,
        "environment": settings.ENVIRONMENT,
        "otp_method": "email" if settings.should_send_email else "console",
        "expires_in_seconds": settings.OTP_EXPIRY_SECONDS,
    }


@router.post("/verify-otp")
def verify_user(email: str, otp: int, db: Session = Depends(get_db)):
    """Verify OTP with environment-aware logic"""
    if not verify_otp(email, otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    user = _get_active_user_by_email(db, email)
    return _issue_user_login_response(user, db)


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the currently authenticated user's profile plus tenant context.

    Frontend usage (Option 1):
    - call this after login
    - use `company_slug` to build `/{company_slug}/...` API paths
    """
    company_slug = None
    company_name = None
    if getattr(current_user, "company_id", None) is not None:
        company = (
            db.query(Company)
            .filter(
                Company.company_id == int(current_user.company_id),
                Company.is_deleted == False,  # noqa: E712
            )
            .first()
        )
        if company:
            company_slug = company.company_slug
            company_name = company.company_name

    role_value = _role_value(current_user)

    return {
        "user_id": int(current_user.user_id),
        "employee_id": current_user.employee_id,
        "email": current_user.email,
        "name": current_user.name,
        "role": role_value,
        "department": current_user.department,
        "designation": current_user.designation,
        "joining_date": current_user.joining_date.isoformat() if current_user.joining_date else None,
        "profile_photo": current_user.profile_photo,
        "is_active": bool(current_user.is_active),
        "is_pin_set": bool(getattr(current_user, "is_pin_set", False)),
        "requires_pin_setup": not bool(getattr(current_user, "is_pin_set", False)),
        "company_id": int(current_user.company_id) if current_user.company_id is not None else None,
        "branch_id": int(current_user.branch_id) if current_user.branch_id is not None else None,
        "company_slug": company_slug,
        "company_name": company_name,
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

    return {
        **get_environment_info(),
        **get_pin_environment_info(),
    }


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
