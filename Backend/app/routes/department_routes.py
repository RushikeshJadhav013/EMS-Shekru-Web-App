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
    
    # Get the old manager before update
    old_manager_id = dept.manager_id
    
    # Update the department
    updated_dept = update_department(db, dept, dept_in)
    
    # Handle manager role synchronization
    new_manager_id = updated_dept.manager_id
    
    if old_manager_id != new_manager_id:
        # If old manager exists, potentially demote them (only if they're not managing other departments)
        if old_manager_id:
            other_depts_with_old_manager = db.query(Department).filter(
                Department.manager_id == old_manager_id,
                Department.id != dept_id
            ).count()
            
            if other_depts_with_old_manager == 0:
                # Old manager is not managing any other departments, demote to Employee
                old_manager = db.query(User).filter(User.user_id == old_manager_id).first()
                if old_manager and old_manager.role in [RoleEnum.MANAGER, RoleEnum.TEAM_LEAD]:
                    old_manager.role = RoleEnum.EMPLOYEE
                    db.commit()
        
        # If new manager exists, promote them to Manager
        if new_manager_id:
            new_manager = db.query(User).filter(User.user_id == new_manager_id).first()
            if new_manager and new_manager.role != RoleEnum.MANAGER:
                new_manager.role = RoleEnum.MANAGER
                db.commit()
    
    return updated_dept


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


@router.get("/names")
def get_department_names(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get basic department names for all authenticated users.
    This is used for dropdowns, filters, and week-off planners.
    """
    departments = list_departments(db)
    return [{"name": dept.name, "code": dept.code} for dept in departments]


@router.get("/managers")
def get_department_managers(
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
):
    # ✅ Include HR, Manager, and TeamLead roles as potential department managers
    # ✅ Exclude Admin users - Admin is the boss and should not be assigned to departments
    managers = (
        db.query(User)
        .filter(User.role.in_([RoleEnum.HR, RoleEnum.MANAGER, RoleEnum.TEAM_LEAD]))
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
    # First, get raw department data and clean it
    raw_user_departments = (
        db.query(User.department, func.count(User.user_id).label('count'))
        .filter(User.department.isnot(None))
        .filter(User.department != '')
        .group_by(User.department)
        .all()
    )
    
    # Consolidate departments with same cleaned names
    consolidated_departments = {}
    for dept_name, user_count in raw_user_departments:
        dept_name_clean = dept_name.strip()
        dept_name_lower = dept_name_clean.lower()
        
        if dept_name_lower in consolidated_departments:
            # Add to existing count
            consolidated_departments[dept_name_lower]['count'] += user_count
        else:
            # New department
            consolidated_departments[dept_name_lower] = {
                'name': dept_name_clean,
                'count': user_count
            }
    
    # Get existing departments
    existing_departments = {dept.name.lower(): dept for dept in db.query(Department).all()}
    
    created_count = 0
    updated_count = 0
    departments_created = []
    
    for dept_name_lower, dept_info in consolidated_departments.items():
        dept_name_clean = dept_info['name']
        user_count = dept_info['count']
        
        if dept_name_lower not in existing_departments:
            # Create new department
            # Generate a code from the department name
            code = ''.join(word[0].upper() for word in dept_name_clean.split()[:3])
            if not code:
                code = dept_name_clean[:3].upper()
            
            # Ensure code is unique
            base_code = code
            counter = 1
            while db.query(Department).filter(Department.code == code).first():
                code = f"{base_code}{counter}"
                counter += 1
            
            new_dept = Department(
                name=dept_name_clean,
                code=code,
                description=f"Auto-created from user departments",
                status="active",
                employee_count=user_count,
                manager_id=None,
                budget=None,
                location=None
            )
            db.add(new_dept)
            departments_created.append(dept_name_clean)
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
        "total_departments": len(consolidated_departments)
    }


