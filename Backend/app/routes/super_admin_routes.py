from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.crud.super_admin_crud import (
    get_total_companies,
    get_total_owners,
    get_company_employee_counts,
    create_super_admin,
    update_super_admin,
    delete_super_admin,
    get_super_admin,
    list_super_admins
)
from app.schemas.super_admin_schema import SuperAdminCreate, SuperAdminUpdate
from app.models.super_admin_model import SuperAdmin
from app.utils.token_utils import create_token
from typing import List

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])

@router.get("/total-companies")
def total_companies(db: Session = Depends(get_db)):
    try:
        return {"total_companies": get_total_companies(db)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/total-owners")
def total_owners(db: Session = Depends(get_db)):
    try:
        return {"total_owners": get_total_owners(db)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/company-employee-counts")
def company_employee_counts(db: Session = Depends(get_db)):
    try:
        return get_company_employee_counts(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create", response_model=SuperAdminCreate)
def create_super_admin_route(super_admin: SuperAdminCreate, db: Session = Depends(get_db)):
    return create_super_admin(db, super_admin)

@router.put("/update/{super_admin_id}", response_model=SuperAdminUpdate)
def update_super_admin_route(super_admin_id: int, super_admin: SuperAdminUpdate, db: Session = Depends(get_db)):
    updated_admin = update_super_admin(db, super_admin_id, super_admin)
    if not updated_admin:
        raise HTTPException(status_code=404, detail="Super Admin not found")
    return updated_admin

@router.delete("/delete/{super_admin_id}")
def delete_super_admin_route(super_admin_id: int, db: Session = Depends(get_db)):
    deleted_admin = delete_super_admin(db, super_admin_id)
    if not deleted_admin:
        raise HTTPException(status_code=404, detail="Super Admin not found")
    return {"detail": "Super Admin deleted"}

@router.get("/view/{super_admin_id}", response_model=SuperAdminCreate)
def get_super_admin_route(super_admin_id: int, db: Session = Depends(get_db)):
    admin = get_super_admin(db, super_admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Super Admin not found")
    return admin

@router.get("/list", response_model=List[SuperAdminCreate])
def list_super_admins_route(db: Session = Depends(get_db)):
    return list_super_admins(db)

@router.post("/login")
def login_super_admin(email: str, db: Session = Depends(get_db)):
    admin = db.query(SuperAdmin).filter(SuperAdmin.email == email).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Super Admin not found")
    # Assuming a token creation process
    token = create_token({"sub": admin.email})
    return {"access_token": token, "token_type": "bearer"}
