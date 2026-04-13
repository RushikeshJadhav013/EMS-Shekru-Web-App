from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud.company_crud import get_company
from app.crud.company_salary_structure_crud import (
    create_company_salary_structure,
    delete_company_salary_structure,
    get_company_salary_structure,
    get_company_salary_structure_by_name,
    get_company_salary_structure_entity,
    list_company_salary_structures,
    update_company_salary_structure,
)
from app.db.database import get_db
from app.db.models.super_admin import SuperAdmin
from app.dependencies import get_current_super_admin
from app.schemas.company_salary_structure_schema import (
    CompanySalaryStructureCreate,
    CompanySalaryStructurePatch,
    CompanySalaryStructureOut,
    CompanySalaryStructureUpdate,
)

router = APIRouter(prefix="/companies", tags=["Company Salary Structures"])


def _ensure_company_exists(db: Session, company_id: int) -> None:
    if not get_company(db, company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")


@router.post(
    "/{company_id}/salary-structures",
    response_model=CompanySalaryStructureOut,
    status_code=status.HTTP_201_CREATED,
)
def create_company_salary_structure_route(
    company_id: int,
    payload: CompanySalaryStructureCreate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    _ensure_company_exists(db, company_id)
    duplicate = get_company_salary_structure_by_name(db, company_id, payload.structure_name)
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Salary structure name already exists for this company",
        )
    return create_company_salary_structure(db, company_id, payload, current_super_admin.super_admin_id)


@router.get("/{company_id}/salary-structures", response_model=List[CompanySalaryStructureOut])
def list_company_salary_structures_route(
    company_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    _ensure_company_exists(db, company_id)
    return list_company_salary_structures(db, company_id)


@router.get("/{company_id}/salary-structures/{structure_id}", response_model=CompanySalaryStructureOut)
def get_company_salary_structure_route(
    company_id: int,
    structure_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    _ensure_company_exists(db, company_id)
    structure = get_company_salary_structure_entity(db, structure_id)
    if not structure or structure.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary structure not found")
    result = get_company_salary_structure(db, structure_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary structure not found")
    return result


@router.put("/{company_id}/salary-structures/{structure_id}", response_model=CompanySalaryStructureOut)
def update_company_salary_structure_route(
    company_id: int,
    structure_id: int,
    payload: CompanySalaryStructureUpdate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    _ensure_company_exists(db, company_id)
    structure = get_company_salary_structure_entity(db, structure_id)
    if not structure or structure.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary structure not found")

    duplicate = get_company_salary_structure_by_name(
        db,
        company_id=company_id,
        structure_name=payload.structure_name,
        exclude_structure_id=structure_id,
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Salary structure name already exists for this company",
        )

    updated = update_company_salary_structure(db, structure_id, payload, current_super_admin.super_admin_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary structure not found")
    return updated


@router.patch("/{company_id}/salary-structures/{structure_id}", response_model=CompanySalaryStructureOut)
def patch_company_salary_structure_route(
    company_id: int,
    structure_id: int,
    payload: CompanySalaryStructurePatch,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    _ensure_company_exists(db, company_id)
    structure = get_company_salary_structure_entity(db, structure_id)
    if not structure or structure.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary structure not found")

    current = get_company_salary_structure(db, structure_id)
    if not current:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary structure not found")

    patch_data = payload.model_dump(exclude_unset=True)
    if not patch_data:
        return current

    merged = current.model_dump()
    merged.update(patch_data)

    validated_update = CompanySalaryStructureUpdate(**merged)

    duplicate = get_company_salary_structure_by_name(
        db,
        company_id=company_id,
        structure_name=validated_update.structure_name,
        exclude_structure_id=structure_id,
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Salary structure name already exists for this company",
        )

    updated = update_company_salary_structure(
        db,
        structure_id,
        validated_update,
        current_super_admin.super_admin_id,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary structure not found")
    return updated


@router.delete("/{company_id}/salary-structures/{structure_id}", status_code=status.HTTP_200_OK)
def delete_company_salary_structure_route(
    company_id: int,
    structure_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin),
):
    _ensure_company_exists(db, company_id)
    structure = get_company_salary_structure_entity(db, structure_id)
    if not structure or structure.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary structure not found")
    delete_company_salary_structure(db, structure_id)
    return {"message": "Salary structure deleted successfully"}
