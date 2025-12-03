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


@router.post("/sync-from-users", status_code=status.HTTP_200_OK)
def sync_departments_from_users(
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
):
    """
    Auto-detect departments from existing users and create department entries.
    Scans all users, finds unique department names, and creates missing departments.
    """
    from app.db.models.department import Department
    from sqlalchemy import func
    
    # Get all unique department names from users (excluding None/empty)
    user_departments = (
        db.query(User.department, func.count(User.user_id).label('count'))
        .filter(User.department.isnot(None))
        .filter(User.department != '')
        .group_by(User.department)
        .all()
    )
    
    # Get existing departments
    existing_departments = {dept.name.lower(): dept for dept in db.query(Department).all()}
    
    created_count = 0
    updated_count = 0
    departments_created = []
    
    for dept_name, user_count in user_departments:
        dept_name_lower = dept_name.lower()
        
        if dept_name_lower not in existing_departments:
            # Create new department
            # Generate a code from the department name
            code = ''.join(word[0].upper() for word in dept_name.split()[:3])
            if not code:
                code = dept_name[:3].upper()
            
            # Ensure code is unique
            base_code = code
            counter = 1
            while db.query(Department).filter(Department.code == code).first():
                code = f"{base_code}{counter}"
                counter += 1
            
            new_dept = Department(
                name=dept_name,
                code=code,
                description=f"Auto-created from user departments",
                status="active",
                employee_count=user_count,
                manager_id=None,
                budget=None,
                location=None
            )
            db.add(new_dept)
            departments_created.append(dept_name)
            created_count += 1
        else:
            # Update employee count for existing department
            existing_dept = existing_departments[dept_name_lower]
            if existing_dept.employee_count != user_count:
                existing_dept.employee_count = user_count
                updated_count += 1
    
    db.commit()
    
    return {
        "message": "Department sync completed",
        "created": created_count,
        "updated": updated_count,
        "departments_created": departments_created,
        "total_departments": len(user_departments)
    }


