from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.department import Department
from app.schemas.department_schema import DepartmentOut, DepartmentCreate, DepartmentUpdate, DepartmentStatusUpdate
from app.crud.department_crud import (
    list_departments,
    get_department,
    create_department,
    update_department,
    delete_department,
)
from app.dependencies import get_current_user, get_tenant_scope, require_roles
from app.enums import RoleEnum
from app.utils.department_utils import normalize_department_string, department_tokens_lower


router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("/", response_model=List[DepartmentOut])
def get_departments(
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    return list_departments(db, company_id=scope["company_id"], branch_id=scope.get("branch_id"))


@router.post("/", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department_endpoint(
    dept_in: DepartmentCreate,
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    try:
        return create_department(db, dept_in, company_id=scope["company_id"], branch_id=scope.get("branch_id"))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{dept_id}", response_model=DepartmentOut)
def update_department_endpoint(
    dept_id: int,
    dept_in: DepartmentUpdate,
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    dept = get_department(db, dept_id, company_id=scope["company_id"], branch_id=scope.get("branch_id"))
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    
    # Get the old manager before update
    old_manager_id = dept.manager_id
    
    # Update the department
    try:
        updated_dept = update_department(
            db,
            dept,
            dept_in,
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    # Handle manager role synchronization
    new_manager_id = updated_dept.manager_id
    
    if old_manager_id != new_manager_id:
        # If old manager exists, potentially demote them (only if they're not managing other departments)
        if old_manager_id:
            other_depts_with_old_manager = db.query(Department).filter(
                Department.manager_id == old_manager_id,
                Department.id != dept_id,
                Department.company_id == int(scope["company_id"]),
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


@router.patch("/{dept_id}/status", response_model=DepartmentOut)
def update_department_status_endpoint(
    dept_id: int,
    status_in: DepartmentStatusUpdate,
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    dept = get_department(db, dept_id, company_id=scope["company_id"], branch_id=scope.get("branch_id"))
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    if status_in.status not in ("active", "inactive"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Must be 'active' or 'inactive'.",
        )

    dept.status = status_in.status
    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department_endpoint(
    dept_id: int,
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    dept = get_department(db, dept_id, company_id=scope["company_id"], branch_id=scope.get("branch_id"))
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    delete_department(db, dept)
    return None


@router.get("/names")
def get_department_names(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Get basic department names for all authenticated users.
    This is used for dropdowns, filters, and week-off planners.
    """
    # current_user is still used for auth; scoping is enforced via get_tenant_scope
    departments = list_departments(db, company_id=scope["company_id"], branch_id=scope.get("branch_id"))
    return [{"name": dept.name, "code": dept.code} for dept in departments]


@router.get("/managers")
def get_department_managers(
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    # ✅ Include HR, Manager, and TeamLead roles as potential department managers
    # ✅ Exclude Admin users - Admin is the boss and should not be assigned to departments
    q = (
        db.query(User)
        .filter(User.role.in_([RoleEnum.HR, RoleEnum.MANAGER, RoleEnum.TEAM_LEAD]))
        .filter(User.is_active.is_(True))
        .filter(User.company_id == scope["company_id"])
    )
    if scope.get("branch_id") is not None:
        q = q.filter(User.branch_id == scope["branch_id"])
    managers = q.order_by(User.name.asc()).all()

    return [
        {
            "id": manager.user_id,
            "name": manager.name,
            "email": manager.email,
            # Normalize and validate comma-separated multiple departments
            # Example stored: "sales, HR , it" -> "Sales, Hr, It"
            "department": normalize_department_string(manager.department),
            # Also expose parsed lowercase tokens for consumers that need them
            "department_tokens": department_tokens_lower(manager.department),
            "role": manager.role.value if hasattr(manager.role, "value") else manager.role,
        }
        for manager in managers
    ]


@router.post("/sync-from-users", status_code=status.HTTP_200_OK)
def sync_departments_from_users(
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Auto-detect departments from existing users and create department entries.
    Scans all users, finds unique department names, and creates missing departments.
    """
    company_id = int(scope["company_id"])

    # Get all user department strings and split into tokens, normalizing each token.
    q = (
        db.query(User.department)
        .filter(User.is_active.is_(True))
        .filter(User.company_id == scope["company_id"])
        .filter(User.department.isnot(None))
        .filter(User.department != "")
    )
    if scope.get("branch_id") is not None:
        q = q.filter(User.branch_id == scope["branch_id"])
    raw_user_departments = q.all()

    # Count per individual department token (handles comma-separated multi-dept values)
    consolidated_departments = {}
    for (dept_val,) in raw_user_departments:
        tokens = department_tokens_lower(dept_val)
        for tok in tokens:
            if not tok:
                continue
            if tok in consolidated_departments:
                consolidated_departments[tok]['count'] += 1
            else:
                # store display name as normalized (First letter upper)
                consolidated_departments[tok] = {
                    'name': normalize_department_string(tok),
                    'count': 1
                }
    
    # Get existing departments
    # Restrict "existing departments" to the same tenant-derived scope to avoid cross-tenant collisions
    existing_departments = {
        dept.name.lower(): dept
        for dept in list_departments(db, company_id=scope["company_id"], branch_id=scope.get("branch_id"))
    }
    
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
            while (
                db.query(Department)
                .filter(Department.code == code, Department.company_id == company_id)
                .first()
            ):
                code = f"{base_code}{counter}"
                counter += 1
            
            new_dept = Department(
                company_id=company_id,
                name=dept_name_clean,
                code=code,
                description="Auto-created from user departments",
                status="active",
                employee_count=user_count,
                manager_id=None,
                location=None,
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


