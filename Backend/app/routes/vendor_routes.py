
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies import get_tenant_scope, require_roles
from app.enums import RoleEnum
from app.db.models.user import User
from app.crud import vendor_crud
from app.schemas.vendor_schema import (
    VendorCreate,
    VendorUpdate,
    VendorResponse,
)


router = APIRouter(
    prefix="/vendors",
    tags=["Vendors"],
)


@router.post(
    "/",
    response_model=VendorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    return vendor_crud.create_vendor(
        db=db,
        company_id=int(scope["company_id"]),
        vendor_name=payload.vendor_name,
        contact_person=payload.contact_person,
        email=payload.email,
        phone=payload.phone,
        address=payload.address,
    )


@router.get(
    "/",
    response_model=list[VendorResponse],
)
def get_vendors(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    return vendor_crud.get_vendors(
        db=db,
        company_id=int(scope["company_id"]),
    )


@router.get(
    "/{vendor_id}",
    response_model=VendorResponse,
)
def get_vendor(
    vendor_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    vendor = vendor_crud.get_vendor(
        db=db,
        vendor_id=vendor_id,
        company_id=int(scope["company_id"]),
    )

    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found.",
        )

    return vendor


@router.put(
    "/{vendor_id}",
    response_model=VendorResponse,
)
def update_vendor(
    payload: VendorUpdate,
    vendor_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update.",
        )

    vendor = vendor_crud.get_vendor(
        db=db,
        vendor_id=vendor_id,
        company_id=int(scope["company_id"]),
    )

    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found.",
        )

    return vendor_crud.update_vendor(
        db=db,
        vendor=vendor,
        **update_data,
    )


@router.delete(
    "/{vendor_id}",
    status_code=status.HTTP_200_OK,
)
def delete_vendor(
    vendor_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    vendor = vendor_crud.get_vendor(
        db=db,
        vendor_id=vendor_id,
        company_id=int(scope["company_id"]),
    )

    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found.",
        )

    vendor_crud.delete_vendor(
        db=db,
        vendor=vendor,
    )

    return {"message": "Vendor deleted successfully."}
