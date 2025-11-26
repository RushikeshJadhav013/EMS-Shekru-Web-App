from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Union
from pathlib import Path
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
from app.enums import RoleEnum
from app.db.models.user import User
import os
import shutil
from datetime import datetime
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
    gender: Optional[str] = Form(None),
    resignation_date: Optional[datetime] = Form(None),
    pan_card: Optional[str] = Form(None),
    aadhar_card: Optional[str] = Form(None),
    shift_type: Optional[str] = Form(None),
    employee_type: Optional[str] = Form(None),  # ✅ Added
    profile_photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):

    email = email.strip()
    employee_id = employee_id.strip()
    pan_card = pan_card.strip().upper() if pan_card else None
    aadhar_card = aadhar_card.strip() if aadhar_card else None

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

    user_in = UserCreate(
        name=name,
        email=email,
        employee_id=employee_id,
        department=department,
        designation=designation,
        phone=phone,
        address=address,
        role=role,
        gender=gender,
        resignation_date=resignation_date,
        pan_card=pan_card,
        aadhar_card=aadhar_card,
        shift_type=shift_type,
        employee_type=employee_type,  # ✅ Added
        profile_photo=profile_photo_path
    )

    try:
        created_user = create_user(db, user_in)
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
    search: Optional[str] = Query(None, description="Search by name, email or department"),
    department: Optional[str] = Query(None, description="Filter by department"),
    role: Optional[RoleEnum] = Query(None, description="Filter by role")
):
    employees = list_users(db)  # ✅ fetch all users properly (no .query(list_users))

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
    role: str = Form("Employee"),
    gender: Optional[str] = Form(None),
    resignation_date: Optional[str] = Form(None),
    pan_card: Optional[str] = Form(None),
    aadhar_card: Optional[str] = Form(None),
    shift_type: Optional[str] = Form(None),
    employee_type: Optional[str] = Form(None),
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

    # Check for duplicate phone number (excluding current employee)
    if phone and phone.strip():
        existing_phone = get_user_by_phone(db, phone.strip())
        if existing_phone and existing_phone.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already exists. Please enter a unique phone number.",
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
    
    # ✅ Only Admin/HR can change roles
    if current_user.role in [RoleEnum.ADMIN, RoleEnum.HR]:
        employee.role = role
    
    employee.gender = gender
    employee.resignation_date = resignation_date
    employee.pan_card = pan_card
    employee.aadhar_card = aadhar_card
    employee.shift_type = shift_type
    employee.employee_type = employee_type
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

@router.get("/export/pdf", summary="Download all user details as PDF")
def download_users_pdf(
    db: Session = Depends(get_db),
    # _: RoleEnum = Depends(require_roles([RoleEnum.ADMIN, RoleEnum.HR])) # Example for role-based access
):
    try:
        pdf_buffer = export_users_pdf(db)
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=\"employees_report.pdf\"",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except Exception as e:
        print(f"Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

@router.get("/export/csv", summary="Download all user details as CSV")
def download_users_csv(
    db: Session = Depends(get_db),
    # _: RoleEnum = Depends(require_roles([RoleEnum.ADMIN, RoleEnum.HR])) # Example for role-based access
):
    csv_buffer = export_users_csv(db)
    return Response(
        content=csv_buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=\"users_report.csv\""
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

# ✅ Admin & HR: Get single employee by ID
@router.get("/{user_id}", response_model=UserOut)
def get_single_employee(user_id: int, db: Session = Depends(get_db),
                        _: RoleEnum = Depends(require_roles([RoleEnum.ADMIN, RoleEnum.HR]))):
    employee = get_user(db, user_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return _sanitize_users_response(employee)
