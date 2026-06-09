from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Union, Literal
from pathlib import Path
from app.utils.timezone import now_ist
from app.schemas.user_schema import (
    UserCreate,
    UserOut,
    UpdateRoleSchema,
    UpdateStatusSchema,
    BulkUpdateStatusSchema,
    validate_employment_dates,
    EMPLOYMENT_DATE_ORDER_MESSAGE,
    user_validation_error_message,
)
from app.crud.user_crud import (
    create_user,
    list_users,
    list_users_scoped,
    update_user_role,
    update_user_status,
    update_users_status_bulk,
    delete_user,
    get_user_by_email,
    get_user_by_employee_id,
    get_user_by_phone,
    get_user_by_pan_card,
    get_user_by_aadhar_card,
    get_user,
    get_user_scoped,
    export_users_pdf,
    export_users_csv,
)
from app.db.database import get_db
from app.dependencies import require_roles, get_current_user, get_tenant_scope
from app.enums import GenderEnum, RoleEnum
from app.db.models.user import User
# Subscription enforcement is done inside create_user() using company/branch scope.
import os
import shutil
from datetime import datetime
import re
from pydantic import EmailStr, ValidationError
from sqlalchemy import func
from starlette.responses import Response
from starlette.background import BackgroundTask
from app.utils.department_utils import normalize_department_string, department_tokens_lower
from app.utils.team_lead_scope import get_team_lead_project_peer_employee_ids
from app.db.models.super_admin import SuperAdmin
from app.db.models.company import Company
from app.db.models.company_branch import CompanyBranch

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _profile_photo_exists(photo_path: Optional[str]) -> bool:
    if not photo_path:
        return False
    candidate = Path(photo_path)
    if not candidate.is_absolute():
        candidate = (BASE_DIR / photo_path).resolve()
    return candidate.exists()


def _parse_optional_form_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse YYYY-MM-DD or ISO datetime from multipart form fields."""
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Invalid date format. Use YYYY-MM-DD or ISO datetime.",
    )


def _build_user_create(**data) -> UserCreate:
    """Build UserCreate from form fields; map Pydantic errors to HTTP 422."""
    try:
        return UserCreate(**data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=user_validation_error_message(exc.errors()),
        ) from None


def _sanitize_user_record(user: User) -> dict:
    data = UserOut.model_validate(user).model_dump()
    if data.get("profile_photo") and not _profile_photo_exists(data["profile_photo"]):
        data["profile_photo"] = None
    return data


def _sanitize_users_response(payload: Union[User, List[User]]) -> Union[dict, List[dict]]:
    if isinstance(payload, list):
        return [_sanitize_user_record(item) for item in payload]
    return _sanitize_user_record(payload)



router = APIRouter(prefix="/employees", tags=["Employees"])

# ✅ Public: Register a new employee
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register_employee(
    name: str = Form(...),
    email: EmailStr = Form(...),
    employee_id: str = Form(...),
    department: Optional[str] = Form(None),
    designation: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    role: Optional[RoleEnum] = Form(RoleEnum.EMPLOYEE),
    # Make gender mandatory on user registration
    gender: str = Form(...),
    resignation_date: Optional[datetime] = Form(None),
    joining_date: Optional[datetime] = Form(None),
    pan_card: Optional[str] = Form(None),
    aadhar_card: Optional[str] = Form(None),
    shift_type: Optional[str] = Form(None),
    employee_type: Optional[str] = Form(None),
    manager_id: Optional[int] = Form(None),  # ✅ Added
    profile_photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):

    email = email.strip().lower()
    employee_id = employee_id.strip()
    pan_card = pan_card.strip().upper() if pan_card else None
    aadhar_card = aadhar_card.strip() if aadhar_card else None
    
    # Validate and convert gender to GenderEnum (mandatory)
    try:
        gender_enum = GenderEnum(gender.strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid gender value. Must be one of: {', '.join([g.value for g in GenderEnum])}"
        )

    # Only Admin and HR can create new users via this endpoint
    if current_user.role not in (RoleEnum.ADMIN, RoleEnum.HR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin or HR users can create new employees"
        )

    # HRs are not permitted to create Admin or HR users
    if current_user.role == RoleEnum.HR and role in (RoleEnum.ADMIN, RoleEnum.HR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HR users are not permitted to create Admin or HR users. Only Admins may do so."
        )

    # Check for duplicate email in users table
    existing_user = get_user_by_email(db, email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee already exists with this email address",
        )
    # Enforce global email uniqueness across users and super admins
    existing_super_admin = (
        db.query(SuperAdmin)
        .filter(func.lower(SuperAdmin.email) == email)
        .first()
    )
    if existing_super_admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address is already used by a super admin",
        )
    
    # Check for duplicate employee_id
    existing_employee = get_user_by_employee_id(db, employee_id)
    if existing_employee:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee already exists with ID '{employee_id}'",
        )

    # Check for duplicate phone number
    if phone and phone.strip():
        normalized_phone = re.sub(r'[^0-9]', '', phone.strip())
        existing_phone = get_user_by_phone(db, normalized_phone)
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already exists. Please enter a unique phone number.",
            )
        existing_super_admin_contact = (
            db.query(SuperAdmin)
            .filter(SuperAdmin.contact_no == normalized_phone)
            .first()
        )
        if existing_super_admin_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a super admin.",
            )
        existing_company_contact = (
            db.query(Company)
            .filter(Company.contact_number == normalized_phone)
            .first()
        )
        if existing_company_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a company.",
            )
        existing_branch_contact = (
            db.query(CompanyBranch)
            .filter(CompanyBranch.contact_number == normalized_phone)
            .first()
        )
        if existing_branch_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a company branch.",
            )

    if pan_card:
        duplicate_pan = get_user_by_pan_card(db, pan_card)
        if duplicate_pan:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="PAN Card already exists. Please enter a unique PAN Card number.",
            )

    if aadhar_card:
        duplicate_aadhar = get_user_by_aadhar_card(db, aadhar_card)
        if duplicate_aadhar:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Aadhar Card already exists. Please enter a unique Aadhar Card number.",
            )

    profile_photo_path = None
    if profile_photo:
        # Create a directory to store profile photos if it doesn't exist
        UPLOAD_DIR = "static/profile_photos"
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        # Generate a unique filename
        file_extension = profile_photo.filename.split('.')[-1]
        file_name = f"{employee_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(profile_photo.file, buffer)
        profile_photo_path = file_path

    # Normalize/validate fields to match schema expectations
    gender_value = gender_enum.value.lower()
    shift_value = (shift_type or "").strip().lower()
    employee_type_value = (employee_type or "").strip().lower()

    if aadhar_card and not re.match(r'^\d{4}-\d{4}-\d{4}$', aadhar_card):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid Aadhar card format. Expected format: 1234-5678-9012",
        )

    # Normalize department to consistent format (First letter uppercase, rest lowercase)
    department_normalized = normalize_department_string(department)

    user_in = _build_user_create(
        name=name,
        email=email,
        employee_id=employee_id,
        department=department_normalized,
        designation=designation,
        phone=phone,
        address=address,
        role=role,
        gender=gender_value,
        resignation_date=resignation_date,
        joining_date=joining_date,
        pan_card=pan_card,
        aadhar_card=aadhar_card,
        shift_type=shift_type,
        employee_type=employee_type,
        manager_id=manager_id,
        profile_photo=profile_photo_path,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )

    try:
        # This endpoint now requires authentication; record creator for auditing/subscription checks
        created_user = create_user(db, user_in, created_by=current_user.user_id)
    except ValueError as e:
        # Handle subscription limit errors
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee already exists with the provided identifiers",
        )
    return _sanitize_users_response(created_user)

# # ✅ Admin & HR: Get all employees with optional search and filter
# @router.get("/", response_model=List[UserOut])
# def get_all_employees(
#     db: Session = Depends(get_db),
#     _: RoleEnum = Depends(require_roles([RoleEnum.ADMIN, RoleEnum.HR])),
#     search: Optional[str] = Query(None, description="Search by name, email or department"),
#     department: Optional[str] = Query(None, description="Filter by department"),
#     role: Optional[RoleEnum] = Query(None, description="Filter by role")
# ):
#     employees = db.query(list_users(db)).all()  # base query

#     # Apply search filter
#     if search:
#         employees = [emp for emp in employees if search.lower() in emp.name.lower() 
#                      or search.lower() in emp.email.lower() 
#                      or (emp.department and search.lower() in emp.department.lower())]

#     # Apply department filter
#     if department:
#         employees = [emp for emp in employees if emp.department == department]

#     # Apply role filter
#     if role:
#         employees = [emp for emp in employees if emp.role == role]

#     return employees

@router.get("/", response_model=List[UserOut])
def get_all_employees_public(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    search: Optional[str] = Query(None, description="Search by name, email or department"),
    department: Optional[str] = Query(None, description="Filter by department"),
    role: Optional[RoleEnum] = Query(None, description="Filter by role"),
    is_active: Literal["true", "false", "all"] = Query("all", description="Filter by active status: 'true', 'false', or 'all' (default)")
):
    """
    Get all employees with role-based access control.
    
    Visibility Rules:
    - Admin: Can view all users
    - HR: Can view HR, Manager, TeamLead, and Employee roles
    - Manager: Can view TeamLead and Employee of their assigned department
    - TeamLead: Can view Employees who share an active project with the TeamLead
    - Employee: Cannot access this endpoint
    """
    employees = list_users_scoped(db, scope["company_id"], scope.get("branch_id"))
    
    # Apply role-based visibility filtering
    if current_user.role == RoleEnum.ADMIN:
        # Admin can view all non-admin users (exclude other admins and themselves)
        employees = [
            emp for emp in employees
            if not (getattr(emp, "role", None) == RoleEnum.ADMIN or getattr(emp, "user_id", None) == current_user.user_id)
        ]
    
    elif current_user.role == RoleEnum.HR:
        # HR list rules:
        # - Cannot see Admins
        # - Cannot see other HRs
        # - Cannot see themselves in the listing
        # HR should only see Managers, TeamLeads, and Employees
        allowed_roles = {RoleEnum.MANAGER, RoleEnum.TEAM_LEAD, RoleEnum.EMPLOYEE}
        employees = [
            emp for emp in employees
            if emp.role in allowed_roles and getattr(emp, "user_id", None) != current_user.user_id
        ]
    
    elif current_user.role == RoleEnum.MANAGER:
        # Manager can view TeamLead and Employee of any of their assigned departments
        allowed_roles = {RoleEnum.TEAM_LEAD, RoleEnum.EMPLOYEE}
        manager_depts = department_tokens_lower(current_user.department)
        employees = [
            emp for emp in employees
            if emp.role in allowed_roles and any(d in department_tokens_lower(emp.department) for d in manager_depts)
        ]
    
    elif current_user.role == RoleEnum.TEAM_LEAD:
        peer_ids = get_team_lead_project_peer_employee_ids(
            db,
            current_user,
            company_id=int(scope["company_id"]),
            branch_id=scope.get("branch_id"),
        )
        employees = [
            emp for emp in employees
            if emp.role == RoleEnum.EMPLOYEE and emp.user_id in peer_ids
        ]
    
    else:
        # Employee role cannot access this endpoint
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employees cannot access the employee directory"
        )

    # Apply search filter
    if search:
        employees = [
            emp for emp in employees
            if search.lower() in emp.name.lower()
            or search.lower() in emp.email.lower()
            or (emp.department and search.lower() in emp.department.lower())
        ]

    # Apply department filter
    if department:
        # Support tokenized matching for comma-separated department strings.
        dept_token = department.strip().lower()
        employees = [
            emp for emp in employees
            if emp.department and dept_token in department_tokens_lower(emp.department)
        ]

    # Apply role filter with hierarchy validation
    if role:
        # Enforce hierarchy rules for explicit role filters so invalid requests get a clear 403
        if current_user.role == RoleEnum.ADMIN and role == RoleEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot view other Admin employees via this endpoint",
            )
        if current_user.role == RoleEnum.HR and role in {RoleEnum.ADMIN, RoleEnum.HR}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HR cannot view Admin/HR employees via this endpoint",
            )
        if current_user.role == RoleEnum.MANAGER and role in {RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers cannot view Admin/HR/Manager employees via this endpoint",
            )
        if current_user.role == RoleEnum.TEAM_LEAD and role != RoleEnum.EMPLOYEE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="TeamLeads can only view Employee role users via this endpoint",
            )

        employees = [emp for emp in employees if emp.role == role]

    # Apply is_active filter (default: True, or 'all' for all employees)
    if is_active != "all":
        is_active_bool = is_active == "true"
        employees = [emp for emp in employees if getattr(emp, "is_active", True) == is_active_bool]

    return _sanitize_users_response(employees)


# ✅ Bulk status update - must be defined before /{user_id} so PUT /employees/status matches here
@router.put("/status", response_model=List[UserOut], summary="Bulk Activate/Deactivate Employees (Admin only)")
def bulk_update_employee_status(
    status_data: BulkUpdateStatusSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN))
):
    """
    Activate or deactivate multiple employees at once.
    Admin only. Cannot change own status or other Admins' status.
    """
    # Reject if self is in the list
    if current_user.user_id in status_data.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change your own status. Remove your user ID ({current_user.user_id}) from the request."
        )
    # Reject if any Admin user IDs are in the list
    target_users = db.query(User).filter(User.user_id.in_(status_data.user_ids)).all()
    admin_users = [u for u in target_users if getattr(u, "role", None) == RoleEnum.ADMIN]
    if admin_users:
        admin_ids = [u.user_id for u in admin_users]
        admin_names = ", ".join(u.name or f"ID {u.user_id}" for u in admin_users)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change status of Admin users. Invalid user IDs: {admin_ids}. Users: {admin_names}"
        )
    # Validate all user_ids exist
    found_ids = {u.user_id for u in target_users}
    not_found = [uid for uid in status_data.user_ids if uid not in found_ids]
    if not_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User(s) not found: {not_found}"
        )
    updated = update_users_status_bulk(
        db, list(status_data.user_ids), status_data.is_active, updated_by=current_user.user_id
    )
    return _sanitize_users_response(updated)


# ✅ Update employee details (Users can update their own profile, Admin/HR can update anyone)
@router.put("/{user_id}", response_model=UserOut)
def update_employee(
    user_id: int,
    name: str = Form(...),
    email: str = Form(...),
    employee_id: str = Form(...),
    department: Optional[str] = Form(None),
    designation: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    role: Optional[RoleEnum] = Form(RoleEnum.EMPLOYEE),
    gender: str = Form(...),
    resignation_date: Optional[str] = Form(None),
    joining_date: Optional[str] = Form(None),
    pan_card: Optional[str] = Form(None),
    aadhar_card: Optional[str] = Form(None),
    shift_type: Optional[str] = Form(None),
    employee_type: Optional[str] = Form(None),
    manager_id: Optional[int] = Form(None),  # ✅ Added
    profile_photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    # Check permissions: User can update their own profile OR must be Admin/HR to update others
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted. You can only update your own profile."
        )
    
    employee = get_user_scoped(db, user_id, scope["company_id"], scope.get("branch_id"))
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # HRs are not permitted to update Admin profiles (except their own)
    if current_user.role == RoleEnum.HR and employee.user_id != current_user.user_id and getattr(employee, "role", None) == RoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HR users are not permitted to modify Admin profiles"
        )

    # Check for duplicate email in users table (excluding current user)
    if email and email.strip():
        normalized_email = email.strip().lower()
        existing_user = get_user_by_email(db, normalized_email)
        if existing_user and existing_user.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Employee already exists with this email address",
            )
        # Enforce global uniqueness against super admins as well
        existing_super_admin = (
            db.query(SuperAdmin)
            .filter(func.lower(SuperAdmin.email) == normalized_email)
            .first()
        )
        if existing_super_admin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email address is already used by a super admin",
            )

    # Check for duplicate employee_id (excluding current user)
    if employee_id and employee_id.strip():
        existing_employee = get_user_by_employee_id(db, employee_id.strip())
        if existing_employee and existing_employee.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee already exists with ID '{employee_id}'",
            )

    # Validate phone format and check for duplicate phone number (excluding current employee)
    digits = None
    if phone and phone.strip():
        digits = re.sub(r'[^0-9]', '', phone)
        if not re.fullmatch(r'[6-9]\d{9}', digits):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Phone number must be exactly 10 digits and start with 6, 7, 8, or 9",
            )
        existing_phone = get_user_by_phone(db, digits)
        if existing_phone and existing_phone.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already exists. Please enter a unique phone number.",
            )
        existing_super_admin_contact = (
            db.query(SuperAdmin)
            .filter(SuperAdmin.contact_no == digits)
            .first()
        )
        if existing_super_admin_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a super admin.",
            )
        existing_company_contact = (
            db.query(Company)
            .filter(Company.contact_number == digits)
            .first()
        )
        if existing_company_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a company.",
            )
        existing_branch_contact = (
            db.query(CompanyBranch)
            .filter(CompanyBranch.contact_number == digits)
            .first()
        )
        if existing_branch_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already used by a company branch.",
            )
    # Validate address (no emojis)
    if address and address.strip():
        addr = address.strip()
        emoji_pattern = re.compile(
            "[" 
            "\U0001F300-\U0001F5FF"
            "\U0001F600-\U0001F64F"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA70-\U0001FAFF"
            "\u2600-\u26FF\u2700-\u27BF"
            "]",
            flags=re.UNICODE,
        )
        if emoji_pattern.search(addr):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Address must not contain emojis",
            )

    # Check for duplicate PAN card (excluding current employee)
    if pan_card and pan_card.strip():
        duplicate_pan = get_user_by_pan_card(db, pan_card.strip())
        if duplicate_pan and duplicate_pan.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="PAN Card already exists. Please enter a unique PAN Card number.",
            )

    # Check for duplicate Aadhar card (excluding current employee)
    if aadhar_card and aadhar_card.strip():
        duplicate_aadhar = get_user_by_aadhar_card(db, aadhar_card.strip())
        if duplicate_aadhar and duplicate_aadhar.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Aadhar Card already exists. Please enter a unique Aadhar Card number.",
            )

    # Handle profile photo upload
    profile_photo_path = employee.profile_photo  # Keep existing photo by default
    if profile_photo and profile_photo.filename:
        try:
            # Create a directory to store profile photos if it doesn't exist
            UPLOAD_DIR = "static/profile_photos"
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            
            # Generate a unique filename
            file_extension = profile_photo.filename.split('.')[-1]
            file_name = f"{employee_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file_extension}"
            file_path = os.path.join(UPLOAD_DIR, file_name)
            
            # Save the file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(profile_photo.file, buffer)
            
            profile_photo_path = file_path
        except Exception as e:
            print(f"Error saving profile photo: {e}")
            # Continue without updating photo if there's an error

    # Update fields
    employee.name = name
    employee.email = email
    employee.employee_id = employee_id
    employee.department = normalize_department_string(department)
    employee.designation = designation
    # store normalized digits if provided
    employee.phone = digits if digits is not None else phone
    employee.address = address
    
    # ✅ Only Admin/HR can change roles with restrictions
    if current_user.role == RoleEnum.ADMIN and role is not None:
        employee.role = role
    elif current_user.role == RoleEnum.HR and role is not None:
        if role == RoleEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HR is not permitted to assign the Admin role. Only Admins may do so."
            )
        if role == RoleEnum.HR and getattr(employee, "role", None) != RoleEnum.HR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HR is not permitted to assign the HR role. Only Admins may do so."
            )
        employee.role = role
    
    # Validate and convert gender to GenderEnum
    # Gender is required for updates
    if gender is None or not str(gender).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gender is required"
        )
    try:
        employee.gender = GenderEnum(gender.strip()).value
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid gender value. Must be one of: {', '.join([g.value for g in GenderEnum])}"
        )
    employee.resignation_date = _parse_optional_form_datetime(resignation_date)
    if joining_date is not None:
        employee.joining_date = _parse_optional_form_datetime(joining_date)
    try:
        validate_employment_dates(employee.joining_date, employee.resignation_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    employee.pan_card = pan_card
    employee.aadhar_card = aadhar_card
    employee.shift_type = shift_type
    employee.employee_type = employee_type
    employee.manager_id = manager_id  # ✅ Added
    employee.profile_photo = profile_photo_path

    db.commit()
    db.refresh(employee)
    return _sanitize_users_response(employee)

# # ✅ Admin only: Update employee role
# @router.put("/{employee_id}/role", response_model=UserOut)
# def update_role(employee_id: int, role_data: UpdateRoleSchema, db: Session = Depends(get_db),
#                 _: RoleEnum = Depends(require_roles([RoleEnum.ADMIN]))):
#     employee = update_user_role(db, employee_id, role_data.role)
#     if not employee:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
#     return employee

# @router.put("/{user_id}/role", response_model=UserOut)
# def update_role_public(
#     user_id: int,
#     role_data: UpdateRoleSchema,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user),
#     scope: dict = Depends(get_tenant_scope),
# ):
#     """
#     Update a user's role.
#     - Admin: can update any user's role (including Admins and self)
#     - HR: can update roles except:
#        * cannot update Admin profiles
#        * cannot update other HR profiles
#        * cannot update their own role
#        * cannot assign the Admin role
#     - Others: forbidden
#     """
#     # Load target user
#     employee = get_user_scoped(db, user_id, scope["company_id"], scope.get("branch_id"))
#     if not employee:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

#     # Admins may do anything
#     if current_user.role == RoleEnum.ADMIN:
#         pass
#     elif current_user.role == RoleEnum.HR:
#         # HR cannot modify Admins or other HRs, and cannot modify self
#         if employee.user_id == current_user.user_id:
#             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HR users cannot modify their own role")
#         if getattr(employee, "role", None) in (RoleEnum.ADMIN, RoleEnum.HR):
#             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HR users cannot modify Admin or other HR profiles")
#         # HR cannot assign Admin role
#         if role_data.role == RoleEnum.ADMIN:
#             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HR users are not permitted to assign the Admin role")
#     else:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Admin or HR users can update roles")

#     updated = update_user_role(db, user_id, role_data.role, updated_by=current_user.user_id)
#     if not updated:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
#     return _sanitize_users_response(updated)


@router.put("/{user_id}/status", response_model=UserOut, summary="Activate/Deactivate Employee")
def update_employee_status(
    user_id: int,
    status_data: UpdateStatusSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Activate or deactivate an employee
    - **user_id**: The ID of the employee
    - **is_active**: True to activate, False to deactivate
    """
    # Load target user for validation
    employee = get_user_scoped(db, user_id, scope["company_id"], scope.get("branch_id"))
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # Only Admin and HR can change status
    if current_user.role not in (RoleEnum.ADMIN, RoleEnum.HR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Admin or HR users can change status")

    # Prevent self status change
    if employee.user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change your own status. User ID {user_id} is your account."
        )

    # Admin cannot change other Admins' status
    if current_user.role == RoleEnum.ADMIN and getattr(employee, "role", None) == RoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change status of Admin users. User ID {user_id} ({employee.name or 'Admin'}) is an Admin."
        )

    # HR restrictions: cannot change status of Admins or other HRs
    if current_user.role == RoleEnum.HR and getattr(employee, "role", None) in (RoleEnum.ADMIN, RoleEnum.HR):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"HR users cannot change status of Admin or HR users. User ID {user_id} has role {getattr(employee, 'role', 'unknown')}."
        )

    updated = update_user_status(db, user_id, status_data.is_active, updated_by=current_user.user_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return _sanitize_users_response(updated)

@router.get("/export/pdf", summary="Download user details as PDF with optional filters")
def download_users_pdf(
    department: Optional[str] = Query(
        None,
        description="Filter by department. Supports comma-separated values (e.g. 'Sales,HR,IT'). Matches users who have at least one of these departments."
    ),
    role: Optional[str] = Query(None, description="Filter by role (e.g., ADMIN, HR, MANAGER, EMPLOYEE)"),
    designation: Optional[str] = Query(None, description="Filter by designation"),
    active_status: Optional[bool] = Query(None, description="Filter by active status (true/false)", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Export employee directory as PDF with optional filters.
    Only Admin and HR can access this endpoint.
    
    Role-based restrictions:
    - Admin: Cannot see self and other admins. Cannot filter by ADMIN role.
    - HR: Cannot see admins, self, and other HRs. Cannot filter by ADMIN or HR roles.
    
    Filters:
    - department: Filter by department name(s). Comma-separated values (e.g. 'Sales,HR'). Matches users who have at least one of these departments (including users with multiple departments).
    - role: Filter by role (HR, MANAGER, TEAM_LEAD, EMPLOYEE for Admin; MANAGER, TEAM_LEAD, EMPLOYEE for HR)
    - designation: Filter by designation
    - status: Filter by active status (true for active, false for inactive)
    
    When no filters are provided, returns the full employee directory.
    """
    # Parse comma-separated department values
    department_filters: Optional[List[str]] = None
    if department:
        tokens = [p.strip() for p in department.split(",") if p and p.strip()]
        if not tokens:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one non-empty department value must be provided when using the department filter"
            )
        department_filters = tokens

    # Validate role filter based on user's role
    if role:
        # Normalize role string to match RoleEnum
        normalized_role = role.strip().upper()
        role_enum = None
        for r in RoleEnum:
            if r.value.upper() == normalized_role or r.name.upper() == normalized_role:
                role_enum = r
                break
        
        if role_enum:
            # Admin cannot filter by ADMIN role
            if current_user.role == RoleEnum.ADMIN and role_enum == RoleEnum.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin role filter is not allowed for Admin users"
                )
            # HR cannot filter by ADMIN or HR roles
            elif current_user.role == RoleEnum.HR and role_enum in {RoleEnum.ADMIN, RoleEnum.HR}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin and HR role filters are not allowed for HR users"
                )
    
    # Apply role-based exclusions
    exclude_user_ids = [current_user.user_id]
    exclude_roles = []
    
    if current_user.role == RoleEnum.ADMIN:
        # Admin cannot see self and other admins
        exclude_roles.append(RoleEnum.ADMIN)
    elif current_user.role == RoleEnum.HR:
        # HR cannot see admins, self, and other HRs
        exclude_roles.extend([RoleEnum.ADMIN, RoleEnum.HR])
    
    try:
        pdf_buffer = export_users_pdf(
            db=db,
            departments=department_filters,
            role=role,
            designation=designation,
            status=active_status,
            exclude_user_ids=exclude_user_ids,
            exclude_roles=exclude_roles,
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )
        
        # Build filename based on filters
        filename_parts = ["employees_report"]
        if department_filters:
            filename_parts.append(f"dept_{'-'.join(department_filters)}")
        if role:
            filename_parts.append(f"role_{role}")
        if designation:
            filename_parts.append(f"desig_{designation}")
        if active_status is not None:
            filename_parts.append(f"status_{'active' if active_status else 'inactive'}")
        
        filename = "_".join(filename_parts) + ".pdf"
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except Exception as e:
        print(f"Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

@router.get("/export/csv", summary="Download user details as CSV with optional filters")
def download_users_csv(
    department: Optional[str] = Query(
        None,
        description="Filter by department. Supports comma-separated values (e.g. 'Sales,HR,IT'). Matches users who have at least one of these departments."
    ),
    role: Optional[str] = Query(None, description="Filter by role"),
    active_status: Optional[bool] = Query(None, description="Filter by active status (true/false)", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Export employee directory as CSV with optional filters.
    Only Admin and HR can access this endpoint.
    
    Role-based restrictions:
    - Admin: Cannot see self and other admins. Cannot filter by ADMIN role.
    - HR: Cannot see admins, self, and other HRs. Cannot filter by ADMIN or HR roles.
    
    Filters:
    - department: Filter by department name(s). Comma-separated values (e.g. 'Sales,HR'). Matches users who have at least one of these departments (including users with multiple departments).
    - role: Filter by role (HR, MANAGER, TEAM_LEAD, EMPLOYEE for Admin; MANAGER, TEAM_LEAD, EMPLOYEE for HR)
    - status: Filter by active status (true for active, false for inactive)
    """
    # Parse comma-separated department values
    department_filters: Optional[List[str]] = None
    if department:
        tokens = [p.strip() for p in department.split(",") if p and p.strip()]
        if not tokens:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one non-empty department value must be provided when using the department filter"
            )
        department_filters = tokens

    # Validate role filter based on user's role
    if role:
        # Normalize role string to match RoleEnum
        normalized_role = role.strip().upper()
        role_enum = None
        for r in RoleEnum:
            if r.value.upper() == normalized_role or r.name.upper() == normalized_role:
                role_enum = r
                break
        
        if role_enum:
            # Admin cannot filter by ADMIN role
            if current_user.role == RoleEnum.ADMIN and role_enum == RoleEnum.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin role filter is not allowed for Admin users"
                )
            # HR cannot filter by ADMIN or HR roles
            elif current_user.role == RoleEnum.HR and role_enum in {RoleEnum.ADMIN, RoleEnum.HR}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin and HR role filters are not allowed for HR users"
                )
    
    # Apply role-based exclusions
    exclude_user_ids = [current_user.user_id]
    exclude_roles = []
    
    if current_user.role == RoleEnum.ADMIN:
        # Admin cannot see self and other admins
        exclude_roles.append(RoleEnum.ADMIN)
    elif current_user.role == RoleEnum.HR:
        # HR cannot see admins, self, and other HRs
        exclude_roles.extend([RoleEnum.ADMIN, RoleEnum.HR])
    
    csv_buffer = export_users_csv(
        db=db,
        departments=department_filters,
        role=role,
        status=active_status,
        exclude_user_ids=exclude_user_ids,
        exclude_roles=exclude_roles,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    
    # Build filename based on filters
    filename_parts = ["users_report"]
    if department_filters:
        filename_parts.append(f"dept_{'-'.join(department_filters)}")
    if role:
        filename_parts.append(f"role_{role}")
    if active_status is not None:
        filename_parts.append(f"status_{'active' if active_status else 'inactive'}")
    
    filename = "_".join(filename_parts) + ".csv"

    return Response(
        content=csv_buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        }
    )


# ✅ Delete employee (requires authentication)
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_employee(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # ✅ Only requires login, no role check
    scope: dict = Depends(get_tenant_scope),
):
    # Optional: Allow users to delete only themselves, or Admin/HR to delete anyone
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted. Only Admin/HR can delete other employees."
        )
    
    # Ensure the target is in-scope before deleting.
    employee = get_user_scoped(db, user_id, scope["company_id"], scope.get("branch_id"))
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    employee = delete_user(db, user_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return None

# ✅ Get single employee by ID (Users can view their own profile, Admin/HR can view anyone)
@router.get("/{user_id}", response_model=UserOut)
def get_single_employee(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    # Load the employee first
    employee = get_user_scoped(db, user_id, scope["company_id"], scope.get("branch_id"))
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # Allow users to view their own profile
    if current_user.user_id == user_id:
        return _sanitize_users_response(employee)

    # HR can view own profile, Managers, TeamLeads, and Employees but not Admins or other HRs
    if current_user.role == RoleEnum.HR:
        if employee.user_id == current_user.user_id:
            return _sanitize_users_response(employee)
        if getattr(employee, "role", None) in {RoleEnum.MANAGER, RoleEnum.TEAM_LEAD, RoleEnum.EMPLOYEE}:
            return _sanitize_users_response(employee)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted. HR cannot view Admin or other HR profiles."
        )

    # Admins: allow viewing non-admins only (cannot view other admins)
    if current_user.role == RoleEnum.ADMIN:
        if getattr(employee, "role", None) == RoleEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted. Admins cannot view other admin profiles."
            )
        return _sanitize_users_response(employee)

    # Other roles: forbidden
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Operation not permitted. You can only view your own profile."
    )


# ✅ Admin: Check subscription status
# @router.get("/subscription/status")
# def get_subscription_status(
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     """Get subscription status for the current admin user"""
#     if current_user.role != RoleEnum.ADMIN:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Only admins can check subscription status"
#         )
    
#     from app.crud.subscription_crud import get_admin_subscription_info
#     return get_admin_subscription_info(db, current_user.user_id)


# ✅ Real-time validation endpoints for form fields
@router.get("/validate/phone/{phone}")
def validate_phone_availability(
    phone: str, 
    exclude_user_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if phone number is available (not already taken)"""
    if not phone or not phone.strip():
        return {"available": True, "message": ""}
    
    phone = phone.strip()
    # Validate format: must start with 6, 7, 8, or 9 and have at least 10 digits
    digits = re.sub(r'[^0-9]', '', phone)
    if len(digits) < 10:
        return {
            "available": False,
            "message": "Phone number must have at least 10 digits"
        }
    if not re.match(r'^[6-9]', digits):
        return {
            "available": False,
            "message": "Phone number must start with 6, 7, 8, or 9"
        }
    
    existing_user = get_user_by_phone(db, digits)
    if existing_user and (exclude_user_id is None or existing_user.user_id != exclude_user_id):
        return {
            "available": False, 
            "message": "Phone number already exists. Please enter a unique phone number."
        }

    existing_super_admin_contact = (
        db.query(SuperAdmin)
        .filter(SuperAdmin.contact_no == digits)
        .first()
    )
    if existing_super_admin_contact:
        return {
            "available": False,
            "message": "Phone number is already used by a super admin.",
        }

    existing_company_contact = (
        db.query(Company)
        .filter(Company.contact_number == digits)
        .first()
    )
    if existing_company_contact:
        return {
            "available": False,
            "message": "Phone number is already used by a company.",
        }

    existing_branch_contact = (
        db.query(CompanyBranch)
        .filter(CompanyBranch.contact_number == digits)
        .first()
    )
    if existing_branch_contact:
        return {
            "available": False,
            "message": "Phone number is already used by a company branch.",
        }
    
    return {"available": True, "message": ""}


@router.get("/validate/pan/{pan_card}")
def validate_pan_availability(
    pan_card: str, 
    exclude_user_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if PAN card is available (not already taken)"""
    if not pan_card or not pan_card.strip():
        return {"available": True, "message": ""}
    
    existing_user = get_user_by_pan_card(db, pan_card.strip().upper())
    if existing_user and (exclude_user_id is None or existing_user.user_id != exclude_user_id):
        return {
            "available": False, 
            "message": "PAN Card already exists. Please enter a unique PAN Card number."
        }
    
    return {"available": True, "message": ""}


@router.get("/validate/aadhar/{aadhar_card}")
def validate_aadhar_availability(
    aadhar_card: str, 
    exclude_user_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if Aadhar card is available (not already taken)"""
    if not aadhar_card or not aadhar_card.strip():
        return {"available": True, "message": ""}
    
    aadhar_card = aadhar_card.strip()
    # Validate format
    if not re.match(r'^\d{4}-\d{4}-\d{4}$', aadhar_card):
        return {
            "available": False,
            "message": "Invalid Aadhar card format. Expected format: 1234-5678-9012"
        }
    
    existing_user = get_user_by_aadhar_card(db, aadhar_card)
    if existing_user and (exclude_user_id is None or existing_user.user_id != exclude_user_id):
        return {
            "available": False, 
            "message": "Aadhar Card already exists. Please enter a unique Aadhar Card number."
        }
    
    return {"available": True, "message": ""}
