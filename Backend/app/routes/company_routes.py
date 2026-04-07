from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
from pydantic import ValidationError
from pathlib import Path
from datetime import datetime
import os
import shutil

from app.db.database import get_db
from app.dependencies import get_current_super_admin
from app.db.models.super_admin import SuperAdmin
from app.db.models.company import Company
from app.db.models.company_branch import CompanyBranch
from app.schemas.company_schema import (
    CompanyCreate,
    CompanyUpdate,
    CompanyOut,
    CompanyStatusUpdate,
)
from app.schemas.company_branch_schema import CompanyBranchOut
from app.schemas.user_schema import UserOut
from app.schemas.company_admin_assignment_schema import (
    CompanyAdminAssignmentCreate,
    CompanyAdminAssignmentOut,
)
from app.crud.company_crud import (
    create_company,
    get_company,
    get_company_by_contact_number,
    get_company_by_email,
    get_company_by_gst_no,
    list_companies,
    update_company,
    set_company_status,
    soft_delete_company,
)
from app.crud.company_branch_crud import list_branches
from app.crud.user_crud import get_user_by_phone
from app.crud.branch_admin_assignment_crud import (
    list_company_assigned_admins,
    get_company_admin_summary,
)
from app.crud.company_admin_assignment_crud import (
    assign_admin_to_company,
    deactivate_company_admin_assignment,
)


router = APIRouter(prefix="/companies", tags=["Companies"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
COMPANY_LOGO_UPLOAD_DIR = "static/company_logos"
ALLOWED_LOGO_CONTENT_TYPES = {"image/jpeg", "image/png", "image/jpg"}


def _format_validation_error(errors: list[dict]) -> str:
    """
    Convert Pydantic validation errors to a short, user-friendly message.
    """
    if not errors:
        return "Invalid input."
    first_error = errors[0]
    field = first_error.get("loc", ["field"])[0]
    message = first_error.get("msg", "Invalid value.")
    # Pydantic messages often start with "Value error, "
    if isinstance(message, str) and message.lower().startswith("value error, "):
        message = message[len("Value error, ") :]
    return f"Invalid {field}: {message}"


def _save_company_logo(logo_file: UploadFile | None, company_name: str) -> str | None:
    if not logo_file:
        return None

    content_type = (logo_file.content_type or "").lower()
    if content_type not in ALLOWED_LOGO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid logo file type. Only JPG and PNG images are allowed.",
        )

    upload_dir = (BASE_DIR / COMPANY_LOGO_UPLOAD_DIR).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    original_ext = Path(logo_file.filename or "").suffix.lower()
    if original_ext not in {".jpg", ".jpeg", ".png"}:
        original_ext = ".png" if content_type == "image/png" else ".jpg"

    safe_company_name = "".join(ch for ch in (company_name or "company") if ch.isalnum())
    if not safe_company_name:
        safe_company_name = "company"

    file_name = f"{safe_company_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}{original_ext}"
    file_path = upload_dir / file_name

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(logo_file.file, buffer)

    # Store relative path in DB for portability
    return os.path.join(COMPANY_LOGO_UPLOAD_DIR, file_name)


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company_route(
    company_name: str = Form(...),
    company_email: str = Form(...),
    contact_number: str = Form(...),
    address: str = Form(...),
    gst_no: str | None = Form(None),
    status_value: bool = Form(True, alias="status"),
    company_logo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    logo_path = _save_company_logo(company_logo, company_name)

    try:
        company = CompanyCreate(
            company_name=company_name,
            company_email=company_email,
            contact_number=contact_number,
            address=address,
            gst_no=gst_no,
            company_logo=logo_path,
            status=status_value,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_format_validation_error(e.errors()),
        )

    existing_contact = get_company_by_contact_number(db, company.contact_number, include_deleted=True)
    if existing_contact:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company contact number already exists",
        )
    existing_user_contact = get_user_by_phone(db, company.contact_number)
    if existing_user_contact:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company contact number is already used by a user/admin.",
        )
    existing_super_admin_contact = (
        db.query(SuperAdmin)
        .filter(SuperAdmin.contact_no == company.contact_number)
        .first()
    )
    if existing_super_admin_contact:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company contact number is already used by a super admin.",
        )
    existing_branch_contact = (
        db.query(CompanyBranch)
        .filter(CompanyBranch.contact_number == company.contact_number)
        .first()
    )
    if existing_branch_contact:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company contact number is already used by a company branch.",
        )

    if company.gst_no:
        existing_gst = get_company_by_gst_no(db, company.gst_no, include_deleted=True)
        if existing_gst:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Company GST number already exists",
            )

    existing = get_company_by_email(db, company.company_email, include_deleted=True)
    if existing and not existing.is_deleted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company email already exists")
    if existing and existing.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company email exists for a deleted company. Use a different email.",
        )

    return create_company(db, company, created_by=current_super_admin.super_admin_id)


@router.get("", response_model=List[CompanyOut])
def list_companies_route(
    include_deleted: bool = False,
    status_filter: bool | None = None,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    return list_companies(db, include_deleted=include_deleted, status=status_filter)


@router.get("/{company_id}", response_model=CompanyOut)
def get_company_route(
    company_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("/{company_id}/branches", response_model=List[CompanyBranchOut])
def list_company_branches_route(
    company_id: int,
    include_deleted: bool = False,
    status_filter: bool | None = None,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    company = get_company(db, company_id, include_deleted=include_deleted)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return list_branches(
        db=db,
        company_id=company_id,
        include_deleted=include_deleted,
        status=status_filter,
    )


@router.get("/{company_id}/admins", response_model=List[UserOut])
def list_company_admins_route(
    company_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return list_company_assigned_admins(db, company_id)


@router.post(
    "/{company_id}/admins",
    response_model=CompanyAdminAssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
def assign_company_admin_route(
    company_id: int,
    payload: CompanyAdminAssignmentCreate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    """Assign an admin to the company directly (works even when the company has no branches)."""
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    try:
        return assign_admin_to_company(
            db=db,
            company_id=company_id,
            admin=payload,
            created_by=current_super_admin.super_admin_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete(
    "/{company_id}/admins/{admin_user_id}",
    response_model=CompanyAdminAssignmentOut,
)
def remove_company_admin_route(
    company_id: int,
    admin_user_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    """Remove direct company-level admin assignment (does not remove branch assignments)."""
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    try:
        return deactivate_company_admin_assignment(
            db=db,
            company_id=company_id,
            admin_user_id=admin_user_id,
            updated_by=current_super_admin.super_admin_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{company_id}/admin-summary")
def get_company_admin_summary_route(
    company_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return get_company_admin_summary(db, company_id)


@router.put("/{company_id}", response_model=CompanyOut)
def update_company_route(
    company_id: int,
    company_name: str | None = Form(None),
    company_email: str | None = Form(None),
    contact_number: str | None = Form(None),
    address: str | None = Form(None),
    gst_no: str | None = Form(None),
    status_value: bool | None = Form(None, alias="status"),
    company_logo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    update_payload: dict = {}
    if company_name is not None:
        update_payload["company_name"] = company_name
    if company_email is not None:
        update_payload["company_email"] = company_email
    if contact_number is not None:
        update_payload["contact_number"] = contact_number
    if address is not None:
        update_payload["address"] = address
    if gst_no is not None:
        update_payload["gst_no"] = gst_no
    if status_value is not None:
        update_payload["status"] = status_value
    if company_logo is not None:
        existing_company = get_company(db, company_id)
        if not existing_company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
        update_payload["company_logo"] = _save_company_logo(
            company_logo, existing_company.company_name
        )

    try:
        company_update = CompanyUpdate(**update_payload)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_format_validation_error(e.errors()),
        )

    if company_update.company_email:
        existing = (
            db.query(Company)
            .filter(
                and_(
                    Company.company_email == company_update.company_email.strip().lower(),
                    Company.company_id != company_id,
                )
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company email already exists")

    if company_update.contact_number:
        normalized_contact = company_update.contact_number.strip()
        existing_contact = (
            db.query(Company)
            .filter(
                Company.contact_number == normalized_contact,
                Company.company_id != company_id,
            )
            .first()
        )
        if existing_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Company contact number already exists",
            )
        existing_user_contact = get_user_by_phone(db, normalized_contact)
        if existing_user_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Company contact number is already used by a user/admin.",
            )
        existing_super_admin_contact = (
            db.query(SuperAdmin)
            .filter(SuperAdmin.contact_no == normalized_contact)
            .first()
        )
        if existing_super_admin_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Company contact number is already used by a super admin.",
            )
        existing_branch_contact = (
            db.query(CompanyBranch)
            .filter(CompanyBranch.contact_number == normalized_contact)
            .first()
        )
        if existing_branch_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Company contact number is already used by a company branch.",
            )

    if company_update.gst_no:
        existing_gst = (
            db.query(Company)
            .filter(
                Company.gst_no == company_update.gst_no.strip().upper(),
                Company.company_id != company_id,
            )
            .first()
        )
        if existing_gst:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Company GST number already exists",
            )

    updated = update_company(db, company_id, company_update, updated_by=current_super_admin.super_admin_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return updated


@router.patch("/{company_id}/status", response_model=CompanyOut)
def set_company_status_route(
    company_id: int,
    payload: CompanyStatusUpdate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    updated = set_company_status(db, company_id, payload.status, updated_by=current_super_admin.super_admin_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return updated


@router.delete("/{company_id}", response_model=CompanyOut)
def soft_delete_company_route(
    company_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    deleted = soft_delete_company(db, company_id, updated_by=current_super_admin.super_admin_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return deleted

