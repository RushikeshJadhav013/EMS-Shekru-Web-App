from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.department import Department
from app.db.models.user import User
from app.schemas.department_schema import DepartmentCreate, DepartmentUpdate
from app.utils.department_utils import department_tokens_lower


def _user_scope_filters(*, company_id: int, branch_id: int | None) -> list:
    clauses = [User.company_id == company_id]
    if branch_id is not None:
        clauses.append(User.branch_id == branch_id)
    return clauses


def _users_in_scope(db: Session, *, company_id: int, branch_id: int | None) -> list[User]:
    return (
        db.query(User)
        .filter(User.is_active.is_(True), *_user_scope_filters(company_id=company_id, branch_id=branch_id))
        .all()
    )


def _department_names_from_users(users: Iterable[User]) -> set[str]:
    """
    Departments are stored on users as comma-separated strings.
    We treat a department record as "in scope" if at least one in-scope user has that token.
    """
    tokens: set[str] = set()
    for u in users:
        tokens.update(department_tokens_lower(getattr(u, "department", None)))
    return {t for t in tokens if t}


def _department_ids_by_manager_in_scope(db: Session, *, company_id: int, branch_id: int | None) -> set[int]:
    rows = (
        db.query(Department.id)
        .join(User, Department.manager_id == User.user_id)
        .filter(
            Department.company_id == int(company_id),
            User.is_active.is_(True),
            *_user_scope_filters(company_id=company_id, branch_id=branch_id),
        )
        .all()
    )
    return {int(dept_id) for (dept_id,) in rows if dept_id is not None}


def _scoped_department_ids(db: Session, *, company_id: int, branch_id: int | None) -> set[int]:
    """Branch-level visibility within a company (manager or user department tokens)."""
    users = _users_in_scope(db, company_id=company_id, branch_id=branch_id)
    name_tokens = _department_names_from_users(users)
    ids: set[int] = set()

    ids.update(_department_ids_by_manager_in_scope(db, company_id=company_id, branch_id=branch_id))

    if name_tokens:
        rows = (
            db.query(Department.id)
            .filter(
                Department.company_id == int(company_id),
                func.lower(Department.name).in_(name_tokens),
            )
            .all()
        )
        ids.update({int(dept_id) for (dept_id,) in rows if dept_id is not None})

    return ids


def list_departments(db: Session, *, company_id: int, branch_id: int | None) -> List[Department]:
    q = db.query(Department).filter(Department.company_id == int(company_id))
    if branch_id is not None:
        scoped_ids = _scoped_department_ids(db, company_id=company_id, branch_id=branch_id)
        if not scoped_ids:
            return []
        q = q.filter(Department.id.in_(scoped_ids))
    return q.order_by(Department.name.asc()).all()


def get_department(db: Session, dept_id: int, *, company_id: int, branch_id: int | None) -> Optional[Department]:
    dept = (
        db.query(Department)
        .filter(Department.id == dept_id, Department.company_id == int(company_id))
        .first()
    )
    if not dept:
        return None
    if branch_id is not None:
        scoped_ids = _scoped_department_ids(db, company_id=company_id, branch_id=branch_id)
        if dept_id not in scoped_ids:
            return None
    return dept


def _get_user_in_scope(db: Session, user_id: int, *, company_id: int, branch_id: int | None) -> Optional[User]:
    return (
        db.query(User)
        .filter(
            User.user_id == user_id,
            User.is_active.is_(True),
            *_user_scope_filters(company_id=company_id, branch_id=branch_id),
        )
        .first()
    )


def _count_employees_in_department(users: Iterable[User], *, department_name: str) -> int:
    target = (department_name or "").strip().lower()
    if not target:
        return 0
    count = 0
    for u in users:
        if target in department_tokens_lower(getattr(u, "department", None)):
            count += 1
    return count


def create_department(db: Session, dept_in: DepartmentCreate, *, company_id: int, branch_id: int | None) -> Department:
    cid = int(company_id)
    if dept_in.manager_id is not None and _get_user_in_scope(
        db, int(dept_in.manager_id), company_id=cid, branch_id=branch_id
    ) is None:
        raise ValueError("Manager not in tenant scope")

    code = (dept_in.code or "").strip()
    if (
        db.query(Department)
        .filter(Department.company_id == cid, func.lower(Department.code) == code.lower())
        .first()
    ):
        raise ValueError("Department code already exists for this company")

    users = _users_in_scope(db, company_id=cid, branch_id=branch_id)

    employee_count = dept_in.employee_count
    if employee_count is None:
        employee_count = _count_employees_in_department(users, department_name=dept_in.name)

    db_dept = Department(
        company_id=cid,
        name=dept_in.name,
        code=code,
        manager_id=dept_in.manager_id,
        description=dept_in.description,
        status=dept_in.status or "active",
        employee_count=employee_count,
        location=dept_in.location,
    )
    db.add(db_dept)
    db.commit()
    db.refresh(db_dept)
    return db_dept


def update_department(
    db: Session,
    dept: Department,
    dept_in: DepartmentUpdate,
    *,
    company_id: int,
    branch_id: int | None,
) -> Department:
    cid = int(company_id)
    data = dept_in.model_dump(exclude_unset=True)

    if "manager_id" in data and data["manager_id"] is not None:
        if _get_user_in_scope(db, int(data["manager_id"]), company_id=cid, branch_id=branch_id) is None:
            raise ValueError("Manager not in tenant scope")

    new_code = data.get("code")
    if new_code is not None:
        code = str(new_code).strip()
        existing = (
            db.query(Department)
            .filter(
                Department.company_id == cid,
                func.lower(Department.code) == code.lower(),
                Department.id != dept.id,
            )
            .first()
        )
        if existing:
            raise ValueError("Department code already exists for this company")
        data["code"] = code

    for field, value in data.items():
        setattr(dept, field, value)

    if "name" in data and "employee_count" not in data:
        users = _users_in_scope(db, company_id=cid, branch_id=branch_id)
        dept.employee_count = _count_employees_in_department(users, department_name=dept.name)

    db.commit()
    db.refresh(dept)
    return dept


def delete_department(db: Session, dept: Department) -> None:
    db.delete(dept)
    db.commit()
