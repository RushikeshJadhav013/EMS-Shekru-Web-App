from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Union
from pathlib import Path
from app.utils.timezone import now_ist
from app.schemas.user_schema import UserCreate, UserOut, UpdateRoleSchema, UpdateStatusSchema
from app.crud.user_crud import (
    create_user,
    list_users,
    update_user_role,
    update_user_status,
    delete_user,
    get_user_by_email,
    get_user_by_employee_id,
    get_user_by_phone,
    get_user_by_pan_card,
    get_user_by_aadhar_card,
    get_user,
    export_users_pdf,
    export_users_csv,
)
from app.db.database import get_db
from app.dependencies import require_roles, get_current_user
from app.enums import GenderEnum, RoleEnum
from app.db.models.user import User
from app.crud.subscription_crud import check_admin_subscription_limit
import os
import shutil
from datetime import datetime
import re
from pydantic import EmailStr
from starlette.responses import Response
from starlette.background import BackgroundTask

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _profile_photo_exists(photo_path: Optional[str]) -> bool:
    if not photo_path:
        return False
    candidate = Path(photo_path)
    if not candidate.is_absolute():
        candidate = (BASE_DIR / photo_path).resolve()
    return candidate.exists()


def _sanitize_user_record(user: User) -> dict:
    data = UserOut.model_validate(user).model_dump()
    if data.get("profile_photo") and not _profile_photo_exists(data["profile_photo"]):
        data["profile_photo"] = None
    return data


def _sanitize_users_response(payload: Union[User, List[User]]) -> Union[dict, List[dict]]:
    if isinstance(payload, list):
        return [_sanitize_user_record(item) for item in payload]
    return _sanitize_user_record(payload)
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
    pan_card: Optional[str] = Form(None),
    aadhar_card: Optional[str] = Form(None),
    shift_type: Optional[str] = Form(None),
    employee_type: Optional[str] = Form(None),
    manager_id: Optional[int] = Form(None),  # ✅ Added
    profile_photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
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

    # Check for duplicate email
    existing_user = get_user_by_email(db, email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee already exists with this email address",
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
        existing_phone = get_user_by_phone(db, phone.strip())
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already exists. Please enter a unique phone number.",
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

    user_in = UserCreate(
        name=name,
        email=email,
        employee_id=employee_id,
        department=department,
        designation=designation,
        phone=phone,
        address=address,
        role=role,
        gender=gender_value,
        resignation_date=resignation_date,
        pan_card=pan_card,
        aadhar_card=aadhar_card,
        shift_type=shift_type,
        employee_type=employee_type,
        manager_id=manager_id,  # ✅ Added
        profile_photo=profile_photo_path
    )

    try:
        # Note: This endpoint doesn't require authentication by default
        # If you want to check subscription limits, make this endpoint require authentication
        # and pass current_user.user_id as created_by
        created_user = create_user(db, user_in, created_by=None)
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
    search: Optional[str] = Query(None, description="Search by name, email or department"),
    department: Optional[str] = Query(None, description="Filter by department"),
    role: Optional[RoleEnum] = Query(None, description="Filter by role")
):
    """
    Get all employees with role-based access control.
    
    Visibility Rules:
    - Admin: Can view all users
    - HR: Can view HR, Manager, TeamLead, and Employee roles
    - Manager: Can view TeamLead and Employee of their assigned department
    - TeamLead: Can view Employees of their assigned teams only
    - Employee: Cannot access this endpoint
    """
    employees = list_users(db)
    
    # Apply role-based visibility filtering
    if current_user.role == RoleEnum.ADMIN:
        # Admin can view all users (including other admins)
        pass  # Keep all employees
    
    elif current_user.role == RoleEnum.HR:
        # HR can view HR, Manager, TeamLead, and Employee roles
        allowed_roles = {RoleEnum.HR, RoleEnum.MANAGER, RoleEnum.TEAM_LEAD, RoleEnum.EMPLOYEE}
        employees = [emp for emp in employees if emp.role in allowed_roles]
    
    elif current_user.role == RoleEnum.MANAGER:
        # Manager can view TeamLead and Employee of their assigned department
        allowed_roles = {RoleEnum.TEAM_LEAD, RoleEnum.EMPLOYEE}
        employees = [
            emp for emp in employees 
            if emp.role in allowed_roles and emp.department == current_user.department
        ]
    
    elif current_user.role == RoleEnum.TEAM_LEAD:
        # TeamLead can view Employees in their department.
        employees = [
            emp for emp in employees
            if emp.role == RoleEnum.EMPLOYEE and emp.department == current_user.department
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
        employees = [emp for emp in employees if emp.department == department]

    # Apply role filter
    if role:
        employees = [emp for emp in employees if emp.role == role]

    return _sanitize_users_response(employees)


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
    gender: Optional[str] = Form(None),
    resignation_date: Optional[str] = Form(None),
    pan_card: Optional[str] = Form(None),
    aadhar_card: Optional[str] = Form(None),
    shift_type: Optional[str] = Form(None),
    employee_type: Optional[str] = Form(None),
    manager_id: Optional[int] = Form(None),  # ✅ Added
    profile_photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check permissions: User can update their own profile OR must be Admin/HR to update others
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted. You can only update your own profile."
        )
    
    employee = get_user(db, user_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # Validate phone format and check for duplicate phone number (excluding current employee)
    if phone and phone.strip():
        digits = re.sub(r'[^0-9]', '', phone)
        if len(digits) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Phone number must have at least 10 digits",
            )
        if not re.match(r'^[6-9]', digits):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Phone number must start with 6, 7, 8, or 9",
            )
        existing_phone = get_user_by_phone(db, phone.strip())
        if existing_phone and existing_phone.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already exists. Please enter a unique phone number.",
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
    employee.department = department
    employee.designation = designation
    employee.phone = phone
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
        employee.role = role
    
    # Validate and convert gender to GenderEnum
    if gender:
        try:
            employee.gender = GenderEnum(gender.strip()).value
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid gender value. Must be one of: {', '.join([g.value for g in GenderEnum])}"
            )
    employee.resignation_date = resignation_date
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

@router.put("/{user_id}/role", response_model=UserOut)
def update_role_public(
    user_id: int,
    role_data: UpdateRoleSchema,
    db: Session = Depends(get_db)
):
    employee = update_user_role(db, user_id, role_data.role)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return _sanitize_users_response(employee)

@router.put("/{user_id}/status", response_model=UserOut, summary="Activate/Deactivate Employee")
def update_employee_status(
    user_id: int,
    status_data: UpdateStatusSchema,
    db: Session = Depends(get_db)
):
    """
    Activate or deactivate an employee
    - **user_id**: The ID of the employee
    - **is_active**: True to activate, False to deactivate
    """
    employee = update_user_status(db, user_id, status_data.is_active)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return _sanitize_users_response(employee)

@router.get("/export/pdf", summary="Download user details as PDF with optional filters")
def download_users_pdf(
    department: Optional[str] = Query(None, description="Filter by department"),
    role: Optional[str] = Query(None, description="Filter by role (e.g., ADMIN, HR, MANAGER, EMPLOYEE)"),
    designation: Optional[str] = Query(None, description="Filter by designation"),
    status: Optional[bool] = Query(None, description="Filter by active status (true/false)"),
    db: Session = Depends(get_db),
    # _: RoleEnum = Depends(require_roles([RoleEnum.ADMIN, RoleEnum.HR])) # Example for role-based access
):
    """
    Export employee directory as PDF with optional filters.
    
    Filters:
    - department: Filter by department name
    - role: Filter by role (ADMIN, HR, MANAGER, TEAM_LEAD, EMPLOYEE)
    - designation: Filter by designation
    - status: Filter by active status (true for active, false for inactive)
    
    When no filters are provided, returns the full employee directory.
    """
    try:
        pdf_buffer = export_users_pdf(
            db=db,
            department=department,
            role=role,
            designation=designation,
            status=status
        )
        
        # Build filename based on filters
        filename_parts = ["employees_report"]
        if department:
            filename_parts.append(f"dept_{department}")
        if role:
            filename_parts.append(f"role_{role}")
        if designation:
            filename_parts.append(f"desig_{designation}")
        if status is not None:
            filename_parts.append(f"status_{'active' if status else 'inactive'}")
        
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
    department: Optional[str] = Query(None, description="Filter by department"),
    role: Optional[str] = Query(None, description="Filter by role"),
    db: Session = Depends(get_db),
    # _: RoleEnum = Depends(require_roles([RoleEnum.ADMIN, RoleEnum.HR])) # Example for role-based access
):
    csv_buffer = export_users_csv(db, department=department, role=role)
    
    # Build filename based on filters
    filename_parts = ["users_report"]
    if department:
        filename_parts.append(f"dept_{department}")
    if role:
        filename_parts.append(f"role_{role}")
    
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
    current_user: User = Depends(get_current_user)  # ✅ Only requires login, no role check
):
    # Optional: Allow users to delete only themselves, or Admin/HR to delete anyone
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted. Only Admin/HR can delete other employees."
        )
    
    employee = delete_user(db, user_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return None

# ✅ Get single employee by ID (Users can view their own profile, Admin/HR can view anyone)
@router.get("/{user_id}", response_model=UserOut)
def get_single_employee(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check permissions: User can view their own profile OR must be Admin/HR to view others
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted. You can only view your own profile."
        )
    
    employee = get_user(db, user_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return _sanitize_users_response(employee)


# ✅ Admin: Check subscription status
@router.get("/subscription/status")
def get_subscription_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get subscription status for the current admin user"""
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can check subscription status"
        )
    
    from app.crud.subscription_crud import get_admin_subscription_info
    return get_admin_subscription_info(db, current_user.user_id)


# ✅ Real-time validation endpoints for form fields
@router.get("/validate/phone/{phone}")
def validate_phone_availability(
    phone: str, 
    exclude_user_id: int = None,
    db: Session = Depends(get_db)
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
    
    existing_user = get_user_by_phone(db, phone)
    if existing_user and (exclude_user_id is None or existing_user.user_id != exclude_user_id):
        return {
            "available": False, 
            "message": "Phone number already exists. Please enter a unique phone number."
        }
    
    return {"available": True, "message": ""}


@router.get("/validate/pan/{pan_card}")
def validate_pan_availability(
    pan_card: str, 
    exclude_user_id: int = None,
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db)
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
