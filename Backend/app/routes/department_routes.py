from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.user import User
from app.schemas.department_schema import DepartmentOut, DepartmentCreate, DepartmentUpdate
from app.crud.department_crud import (
    list_departments,
    get_department,
    create_department,
    update_department,
    delete_department,
)
from app.dependencies import get_current_user, require_roles
from app.enums import RoleEnum


router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("/", response_model=List[DepartmentOut])
def get_departments(
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
):
    return list_departments(db)


@router.post("/", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department_endpoint(
    dept_in: DepartmentCreate,
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
):
    return create_department(db, dept_in)


@router.put("/{dept_id}", response_model=DepartmentOut)
def update_department_endpoint(
    dept_id: int,
    dept_in: DepartmentUpdate,
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
):
    dept = get_department(db, dept_id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return update_department(db, dept, dept_in)


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department_endpoint(
    dept_id: int,
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
):
    dept = get_department(db, dept_id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    delete_department(db, dept)
    return None


@router.get("/managers")
def get_department_managers(
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
):
    managers = (
        db.query(User)
        .filter(User.role.in_([RoleEnum.MANAGER, RoleEnum.TEAM_LEAD]))
        .filter(User.is_active.is_(True))
        .order_by(User.name.asc())
        .all()
    )

    return [
        {
            "id": manager.user_id,
            "name": manager.name,
            "email": manager.email,
            "department": manager.department,
            "role": manager.role.value if hasattr(manager.role, "value") else manager.role,
        }
        for manager in managers
    ]


