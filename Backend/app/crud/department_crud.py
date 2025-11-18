from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.department import Department
from app.db.models.user import User
from app.schemas.department_schema import DepartmentCreate, DepartmentUpdate


def list_departments(db: Session) -> List[Department]:
    return db.query(Department).order_by(Department.name.asc()).all()


def get_department(db: Session, dept_id: int) -> Optional[Department]:
    return db.query(Department).filter(Department.id == dept_id).first()


def create_department(db: Session, dept_in: DepartmentCreate) -> Department:
    # If employee_count is not provided, derive it from users table by department name
    employee_count = dept_in.employee_count
    if employee_count is None:
        employee_count = (
            db.query(func.count(User.user_id))
            .filter(User.department == dept_in.name)
            .scalar()
            or 0
        )

    db_dept = Department(
        name=dept_in.name,
        code=dept_in.code,
        manager_id=dept_in.manager_id,
        description=dept_in.description,
        status=dept_in.status or "active",
        employee_count=employee_count,
        budget=dept_in.budget,
        location=dept_in.location,
    )
    db.add(db_dept)
    db.commit()
    db.refresh(db_dept)
    return db_dept


def update_department(db: Session, dept: Department, dept_in: DepartmentUpdate) -> Department:
    data = dept_in.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(dept, field, value)

    # Optionally re-sync employee_count if not explicitly set but name changed
    if "name" in data and "employee_count" not in data:
        dept.employee_count = (
            db.query(func.count(User.user_id))
            .filter(User.department == dept.name)
            .scalar()
            or 0
        )

    db.commit()
    db.refresh(dept)
    return dept


def delete_department(db: Session, dept: Department) -> None:
    db.delete(dept)
    db.commit()


