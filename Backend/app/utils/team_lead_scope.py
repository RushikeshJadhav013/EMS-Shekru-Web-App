from typing import Optional, Set

from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.project_member import ProjectMember
from app.enums import RoleEnum
from app.utils.department_utils import department_tokens_lower


def _departments_overlap(user_a: User, user_b: User) -> bool:
    tokens_a = set(department_tokens_lower(getattr(user_a, "department", None)))
    tokens_b = set(department_tokens_lower(getattr(user_b, "department", None)))
    return bool(tokens_a and tokens_b and tokens_a.intersection(tokens_b))


def _user_active_project_ids(
    db: Session,
    user_id: int,
    *,
    company_id: int,
) -> list[int]:
    return [
        row[0]
        for row in (
            db.query(ProjectMember.project_id)
            .join(Project, Project.project_id == ProjectMember.project_id)
            .filter(
                ProjectMember.user_id == user_id,
                ProjectMember.is_active.is_(True),
                Project.company_id == int(company_id),
            )
            .all()
        )
    ]


def _team_lead_active_project_ids(
    db: Session,
    team_lead_id: int,
    *,
    company_id: int,
) -> list[int]:
    return _user_active_project_ids(db, team_lead_id, company_id=company_id)


def get_team_lead_managed_employee_ids(
    db: Session,
    team_lead: User,
    *,
    company_id: int,
    branch_id: Optional[int] = None,
) -> Set[int]:
    """
    Employees a TeamLead may manage for leave/WFH purposes:
    same department AND active member of at least one shared project
    where the TeamLead is also an active member.
    """
    lead_tokens = set(department_tokens_lower(getattr(team_lead, "department", None)))
    if not lead_tokens:
        return set()

    lead_project_ids = _team_lead_active_project_ids(
        db, team_lead.user_id, company_id=company_id
    )
    if not lead_project_ids:
        return set()

    query = (
        db.query(User)
        .join(ProjectMember, ProjectMember.user_id == User.user_id)
        .filter(
            ProjectMember.project_id.in_(lead_project_ids),
            ProjectMember.is_active.is_(True),
            User.role == RoleEnum.EMPLOYEE,
            User.is_active.is_(True),
            User.company_id == int(company_id),
            User.user_id != team_lead.user_id,
            User.department.isnot(None),
        )
    )
    if branch_id is not None:
        query = query.filter(User.branch_id == int(branch_id))

    managed: Set[int] = set()
    seen: Set[int] = set()
    for employee in query.all():
        if employee.user_id in seen:
            continue
        seen.add(employee.user_id)
        if _departments_overlap(team_lead, employee):
            managed.add(employee.user_id)
    return managed


_TEAM_LEAD_CHAT_ELEVATED_ROLES = frozenset({
    RoleEnum.ADMIN.value,
    RoleEnum.HR.value,
    RoleEnum.MANAGER.value,
})


def get_employee_project_team_lead_ids(
    db: Session,
    employee: User,
    *,
    company_id: int,
    branch_id: Optional[int] = None,
) -> Set[int]:
    """TeamLeads who share at least one active project with the employee."""
    project_ids = _user_active_project_ids(
        db, employee.user_id, company_id=company_id
    )
    if not project_ids:
        return set()

    query = (
        db.query(User.user_id)
        .join(ProjectMember, ProjectMember.user_id == User.user_id)
        .filter(
            ProjectMember.project_id.in_(project_ids),
            ProjectMember.is_active.is_(True),
            User.role == RoleEnum.TEAM_LEAD,
            User.is_active.is_(True),
            User.company_id == int(company_id),
            User.user_id != employee.user_id,
        )
    )
    if branch_id is not None:
        query = query.filter(User.branch_id == int(branch_id))

    return {int(row[0]) for row in query.distinct().all()}


def get_employee_project_peer_employee_ids(
    db: Session,
    employee: User,
    *,
    company_id: int,
    branch_id: Optional[int] = None,
) -> Set[int]:
    """Other employees who share at least one active project with the employee."""
    project_ids = _user_active_project_ids(
        db, employee.user_id, company_id=company_id
    )
    if not project_ids:
        return set()

    query = (
        db.query(User.user_id)
        .join(ProjectMember, ProjectMember.user_id == User.user_id)
        .filter(
            ProjectMember.project_id.in_(project_ids),
            ProjectMember.is_active.is_(True),
            User.role == RoleEnum.EMPLOYEE,
            User.is_active.is_(True),
            User.company_id == int(company_id),
            User.user_id != employee.user_id,
        )
    )
    if branch_id is not None:
        query = query.filter(User.branch_id == int(branch_id))

    return {int(row[0]) for row in query.distinct().all()}


def employee_can_chat_with_user(
    db: Session,
    employee: User,
    target: User,
    *,
    company_id: int,
    branch_id: Optional[int] = None,
) -> bool:
    """
    Employees may chat privately with Admin, HR, and Manager in the same company,
    plus employees and TeamLeads on shared active projects only.
    """
    if target.user_id == employee.user_id:
        return False
    target_role = getattr(target.role, "value", str(target.role))
    if target_role in {
        RoleEnum.ADMIN.value,
        RoleEnum.HR.value,
        RoleEnum.MANAGER.value,
    }:
        return True
    if target_role == RoleEnum.EMPLOYEE.value:
        return target.user_id in get_employee_project_peer_employee_ids(
            db,
            employee,
            company_id=company_id,
            branch_id=branch_id,
        )
    if target_role == RoleEnum.TEAM_LEAD.value:
        return target.user_id in get_employee_project_team_lead_ids(
            db,
            employee,
            company_id=company_id,
            branch_id=branch_id,
        )
    return False


def team_lead_can_chat_with_user(
    db: Session,
    team_lead: User,
    target: User,
    *,
    company_id: int,
    branch_id: Optional[int] = None,
) -> bool:
    """
    TeamLead may chat with Admin/HR/Manager (any department) plus Employees
    in the same department with a shared active project.
    """
    if target.user_id == team_lead.user_id:
        return False
    target_role = getattr(target.role, "value", str(target.role))
    if target_role in _TEAM_LEAD_CHAT_ELEVATED_ROLES:
        return True
    return team_lead_can_manage_employee(
        db,
        team_lead,
        target,
        company_id=company_id,
        branch_id=branch_id,
    )


def team_lead_can_manage_employee(
    db: Session,
    team_lead: User,
    employee: User,
    *,
    company_id: int,
    branch_id: Optional[int] = None,
) -> bool:
    employee_role = getattr(employee.role, "value", str(employee.role))
    if employee_role != RoleEnum.EMPLOYEE.value:
        return False
    if employee.user_id == team_lead.user_id:
        return False
    return employee.user_id in get_team_lead_managed_employee_ids(
        db,
        team_lead,
        company_id=company_id,
        branch_id=branch_id,
    )


def get_team_lead_project_peer_employee_ids(
    db: Session,
    team_lead: User,
    *,
    company_id: int,
    branch_id: Optional[int] = None,
) -> Set[int]:
    """Employees who share at least one active project with the TeamLead."""
    lead_project_ids = _team_lead_active_project_ids(
        db, team_lead.user_id, company_id=company_id
    )
    if not lead_project_ids:
        return set()

    query = (
        db.query(User.user_id)
        .join(ProjectMember, ProjectMember.user_id == User.user_id)
        .filter(
            ProjectMember.project_id.in_(lead_project_ids),
            ProjectMember.is_active.is_(True),
            User.role == RoleEnum.EMPLOYEE,
            User.is_active.is_(True),
            User.company_id == int(company_id),
            User.user_id != team_lead.user_id,
        )
    )
    if branch_id is not None:
        query = query.filter(User.branch_id == int(branch_id))

    return {int(row[0]) for row in query.distinct().all()}


def get_project_employee_member_ids(
    db: Session,
    project_id: int,
    *,
    company_id: int,
    branch_id: Optional[int] = None,
) -> Set[int]:
    """Active Employee members of a specific project."""
    query = (
        db.query(User.user_id)
        .join(ProjectMember, ProjectMember.user_id == User.user_id)
        .join(Project, Project.project_id == ProjectMember.project_id)
        .filter(
            ProjectMember.project_id == int(project_id),
            ProjectMember.is_active.is_(True),
            Project.company_id == int(company_id),
            User.role == RoleEnum.EMPLOYEE,
            User.is_active.is_(True),
        )
    )
    if branch_id is not None:
        query = query.filter(User.branch_id == int(branch_id))

    return {int(row[0]) for row in query.distinct().all()}


def is_active_project_member(db: Session, project_id: int, user_id: int) -> bool:
    return (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == int(project_id),
            ProjectMember.user_id == int(user_id),
            ProjectMember.is_active.is_(True),
        )
        .first()
        is not None
    )


def team_lead_can_assign_task_to(
    db: Session,
    team_lead: User,
    assignee: User,
    *,
    company_id: int,
    branch_id: Optional[int] = None,
    project_id: Optional[int] = None,
) -> bool:
    if assignee.user_id == team_lead.user_id:
        return True

    assignee_role = getattr(assignee.role, "value", str(assignee.role))
    if assignee_role != RoleEnum.EMPLOYEE.value:
        return False

    if project_id is not None:
        return is_active_project_member(db, int(project_id), assignee.user_id)

    return assignee.user_id in get_team_lead_project_peer_employee_ids(
        db,
        team_lead,
        company_id=company_id,
        branch_id=branch_id,
    )


def team_lead_can_view_task(
    db: Session,
    team_lead: User,
    task,
    *,
    company_id: int,
    branch_id: Optional[int] = None,
) -> bool:
    if team_lead.user_id in (task.assigned_to, task.assigned_by):
        return True

    if task.project_id is not None:
        peer_ids = get_project_employee_member_ids(
            db,
            int(task.project_id),
            company_id=company_id,
            branch_id=branch_id,
        )
    else:
        peer_ids = get_team_lead_project_peer_employee_ids(
            db,
            team_lead,
            company_id=company_id,
            branch_id=branch_id,
        )

    involved = {task.assigned_to, task.assigned_by}
    return bool(peer_ids and involved.intersection(peer_ids))
