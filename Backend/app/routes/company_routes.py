from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List

from app.db.database import get_db
from app.dependencies import get_current_super_admin
from app.db.models.super_admin import SuperAdmin
from app.db.models.company import Company
from app.schemas.company_schema import (
    CompanyCreate,
    CompanyUpdate,
    CompanyOut,
    CompanyStatusUpdate,
)
from app.schemas.company_branch_schema import CompanyBranchOut
from app.schemas.user_schema import UserOut
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
from app.crud.branch_admin_assignment_crud import (
    list_company_assigned_admins,
    get_company_admin_summary,
)


router = APIRouter(prefix="/companies", tags=["Companies"])


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company_route(
    company: CompanyCreate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    existing_contact = get_company_by_contact_number(db, company.contact_number, include_deleted=True)
    if existing_contact:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company contact number already exists",
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
    company_update: CompanyUpdate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
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
        existing_contact = (
            db.query(Company)
            .filter(
                Company.contact_number == company_update.contact_number.strip(),
                Company.company_id != company_id,
            )
            .first()
        )
        if existing_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Company contact number already exists",
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

