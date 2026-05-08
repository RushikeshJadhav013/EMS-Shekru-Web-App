from typing import List, Optional
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.project import Project
from app.db.models.task import Task
from app.db.models.project_member import ProjectMember
from app.db.models.notification import ProjectNotification
from app.db.models.user import User
from app.dependencies import get_current_user, get_tenant_scope, require_roles
from app.enums import RoleEnum
from app.schemas.project_schema import (
    ProjectCreate,
    ProjectUpdate,
    ProjectOut,
    ProjectStatusUpdate,
    ProjectNotificationOut,
)
from app.schemas.project_member_schema import ProjectMemberAdd, ProjectMemberOut, ProjectMembersBulkAdd
from app.utils.timezone import now_ist
from app.utils.department_utils import department_tokens_lower

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


def _user_scope_filters(scope: dict, user_alias=User) -> list:
    clauses = [user_alias.company_id == scope["company_id"]]
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        clauses.append(user_alias.branch_id == branch_id)
    return clauses


def _assert_current_in_scope(db: Session, current_user: User, scope: dict) -> None:
    if current_user.role == RoleEnum.ADMIN:
        # Admin tenant access is assignment-based and validated by get_tenant_scope.
        return
    current = (
        db.query(User.user_id)
        .filter(
            User.user_id == current_user.user_id,
            User.is_active.is_(True),
            *_user_scope_filters(scope),
        )
        .first()
    )
    if not current:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current user is outside selected tenant scope",
        )


def _get_user_in_scope(db: Session, user_id: int, scope: dict) -> Optional[User]:
    return (
        db.query(User)
        .filter(User.user_id == user_id, User.is_active.is_(True), *_user_scope_filters(scope))
        .first()
    )


def _project_in_scope_clause(scope: dict):
    clauses = [Project.company_id == scope["company_id"]]
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        clauses.append(Project.branch_id == branch_id)
    return clauses


def _validate_project_dates(start_date: Optional[date], end_date: Optional[date]) -> None:
    """
    Validate project dates.

    Rules:
    - start_date: can be in the past (no restriction).
    - end_date: cannot be in the past.
    - If both provided, end_date cannot be before start_date.
    """
    today = date.today()

    if end_date is not None and end_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date cannot be in the past.",
        )

    if start_date is not None and end_date is not None and end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date cannot be before start_date.",
        )


def _ensure_project_exists(db: Session, project_id: int, *, scope: dict) -> Project:
    project = (
        db.query(Project)
        .filter(Project.project_id == project_id)
        .filter(*_project_in_scope_clause(scope))
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _active_project_members(
    db: Session,
    project_id: int,
    *,
    scope: dict,
    exclude_user_id: int | None = None,
) -> list[User]:
    query = (
        db.query(User)
        .join(ProjectMember, ProjectMember.user_id == User.user_id)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.is_active.is_(True),
            User.is_active.is_(True),
            *_user_scope_filters(scope),
        )
    )
    if exclude_user_id is not None:
        query = query.filter(User.user_id != exclude_user_id)
    return query.all()


def _create_project_notifications(
    db: Session,
    *,
    recipients: list[User],
    project_id: int | None,
    notification_type: str,
    title: str,
    message: str,
) -> list[ProjectNotification]:
    notifications: list[ProjectNotification] = []
    for recipient in recipients:
        notification = ProjectNotification(
            user_id=recipient.user_id,
            project_id=project_id,
            notification_type=notification_type,
            title=title,
            message=message,
            is_read=False,
        )
        db.add(notification)
        notifications.append(notification)
    if notifications:
        db.commit()
        for notification in notifications:
            db.refresh(notification)
    return notifications


def _notify_project_members(
    db: Session,
    *,
    project: Project,
    actor: User,
    notification_type: str,
    title: str,
    message: str,
    scope: dict,
) -> list[ProjectNotification]:
    recipients = _active_project_members(db, project.project_id, scope=scope, exclude_user_id=actor.user_id)
    return _create_project_notifications(
        db,
        recipients=recipients,
        project_id=project.project_id,
        notification_type=notification_type,
        title=title,
        message=message,
    )


def _list_project_notifications(db: Session, user_id: int, *, scope: dict) -> list[ProjectNotification]:
    return (
        db.query(ProjectNotification)
        .outerjoin(Project, Project.project_id == ProjectNotification.project_id)
        .filter(
            ProjectNotification.user_id == user_id,
            or_(
                ProjectNotification.project_id.is_(None),
                and_(Project.project_id.isnot(None), *_project_in_scope_clause(scope)),
            ),
        )
        .order_by(ProjectNotification.created_at.desc())
        .all()
    )


def _mark_project_notification_as_read(
    db: Session,
    *,
    notification_id: int,
    user_id: int,
    scope: dict,
) -> ProjectNotification | None:
    notification = (
        db.query(ProjectNotification)
        .outerjoin(Project, Project.project_id == ProjectNotification.project_id)
        .filter(
            ProjectNotification.notification_id == notification_id,
            ProjectNotification.user_id == user_id,
            or_(
                ProjectNotification.project_id.is_(None),
                and_(Project.project_id.isnot(None), *_project_in_scope_clause(scope)),
            ),
        )
        .first()
    )
    if not notification:
        return None
    if not notification.is_read:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
    return notification


@router.post(
    "/",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER))],
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Create a new project.

    Person in charge (PIC) is always Admin/HR (current user).
    """
    _assert_current_in_scope(db, current_user, scope)
    _validate_project_dates(payload.start_date, payload.end_date)

    # Managers must have at least one valid department token (supports comma-separated departments)
    if current_user.role == RoleEnum.MANAGER:
        manager_depts = department_tokens_lower(getattr(current_user, "department", None))
        if not manager_depts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Manager must have at least one department assigned to create projects.",
            )

    project = Project(
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="planned",
        person_in_charge_id=current_user.user_id,
        created_by=current_user.user_id,
        is_active=True,
    )

    db.add(project)
    db.flush()

    # Add PIC as project member with role 'pic'
    member = ProjectMember(
        project_id=project.project_id,
        user_id=current_user.user_id,
        role="pic",
        added_by=current_user.user_id,
    )
    db.add(member)

    db.commit()
    db.refresh(project)

    task_count = (
        db.query(Task)
        .filter(Task.project_id == project.project_id)
        .count()
    )

    return ProjectOut(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status,
        is_active=project.is_active,
        person_in_charge_id=project.person_in_charge_id,
        person_in_charge_name=project.person_in_charge.name if project.person_in_charge else None,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        member_count=db.query(ProjectMember).filter(
            ProjectMember.project_id == project.project_id,
            ProjectMember.is_active.is_(True),
        ).count(),
        task_count=task_count,
    )


@router.get("/", response_model=List[ProjectOut])
def list_projects(
    status_filter: Optional[str] = Query(None, description="Filter by project status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    List projects visible to the current user.

    - Admin/HR: see all projects (with optional status filter).
    - Manager/TeamLead/Employee: see only projects where they are active members.
    """
    _assert_current_in_scope(db, current_user, scope)
    # Admin/HR can see all projects
    if current_user.role in (RoleEnum.ADMIN, RoleEnum.HR):
        query = db.query(Project).filter(*_project_in_scope_clause(scope))
    else:
        # Other roles can see only projects where they are active members
        query = (
            db.query(Project)
            .join(
                ProjectMember,
                ProjectMember.project_id == Project.project_id,
            )
            .filter(
                ProjectMember.user_id == current_user.user_id,
                ProjectMember.is_active.is_(True),
            )
            .filter(*_project_in_scope_clause(scope))
            .distinct()
        )

    if status_filter:
        query = query.filter(Project.status == status_filter)

    projects = query.order_by(Project.created_at.desc()).all()

    results: List[ProjectOut] = []
    for project in projects:
        member_count = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project.project_id, ProjectMember.is_active.is_(True))
            .count()
        )
        task_count = (
            db.query(Task)
            .filter(Task.project_id == project.project_id)
            .count()
        )
        results.append(
            ProjectOut(
                project_id=project.project_id,
                name=project.name,
                description=project.description,
                start_date=project.start_date,
                end_date=project.end_date,
                status=project.status,
                is_active=project.is_active,
                person_in_charge_id=project.person_in_charge_id,
                person_in_charge_name=project.person_in_charge.name if project.person_in_charge else None,
                created_by=project.created_by,
                created_at=project.created_at,
                updated_at=project.updated_at,
                member_count=member_count,
                task_count=task_count,
            )
        )

    return results


@router.get("/notifications", response_model=List[ProjectNotificationOut])
def get_project_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, current_user, scope)
    return _list_project_notifications(db, current_user.user_id, scope=scope)


@router.put("/notifications/{notification_id}/read", response_model=ProjectNotificationOut)
def mark_project_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, current_user, scope)
    notification = _mark_project_notification_as_read(
        db,
        notification_id=notification_id,
        user_id=current_user.user_id,
        scope=scope,
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification


@router.get(
    "/{project_id}",
    response_model=ProjectOut,
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Get a specific project by ID.

    - Admin/HR: can access any project.
    - Manager/TeamLead/Employee: can access only projects where they are active members.
    """
    _assert_current_in_scope(db, current_user, scope)
    if current_user.role in (RoleEnum.ADMIN, RoleEnum.HR):
        # Admin/HR can access any project
        project = _ensure_project_exists(db, project_id, scope=scope)
    else:
        # Other roles can access only projects where they are active members
        project = (
            db.query(Project)
            .join(
                ProjectMember,
                ProjectMember.project_id == Project.project_id,
            )
            .filter(
                Project.project_id == project_id,
                ProjectMember.user_id == current_user.user_id,
                ProjectMember.is_active.is_(True),
            )
            .filter(*_project_in_scope_clause(scope))
            .first()
        )
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    member_count = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.project_id, ProjectMember.is_active.is_(True))
        .count()
    )

    task_count = (
        db.query(Task)
        .filter(Task.project_id == project.project_id)
        .count()
    )

    return ProjectOut(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status,
        is_active=project.is_active,
        person_in_charge_id=project.person_in_charge_id,
        person_in_charge_name=project.person_in_charge.name if project.person_in_charge else None,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        member_count=member_count,
        task_count=task_count,
    )


@router.put(
    "/{project_id}",
    response_model=ProjectOut,
    dependencies=[Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER))],
)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Update a project.

    - Admin/HR (PIC roles): can update any project.
    - Manager: can update only projects where they are active members and
      have at least one department assigned (supports comma-separated departments).
    """
    _assert_current_in_scope(db, current_user, scope)
    project = _ensure_project_exists(db, project_id, scope=scope)

    # Managers: enforce department configuration + project ownership
    if current_user.role == RoleEnum.MANAGER:
        manager_depts = department_tokens_lower(getattr(current_user, "department", None))
        if not manager_depts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Manager must have at least one department assigned to update projects.",
            )

        # Manager can update only projects where they are active members
        membership = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.user_id,
                ProjectMember.is_active.is_(True),
            )
            .first()
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers can update only their own projects.",
            )

    # Determine the effective dates after update for validation
    new_start_date = payload.start_date if payload.start_date is not None else project.start_date
    new_end_date = payload.end_date if payload.end_date is not None else project.end_date

    # Allow past dates, but ensure logical ordering
    if new_start_date is not None and new_end_date is not None and new_end_date < new_start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date cannot be before start_date.",
        )

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    _notify_project_members(
        db,
        project=project,
        actor=current_user,
        notification_type="Project Updated",
        title="Project Updated",
        message=f"{current_user.name} updated project '{project.name}'.",
        scope=scope,
    )

    member_count = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.project_id, ProjectMember.is_active.is_(True))
        .count()
    )

    task_count = (
        db.query(Task)
        .filter(Task.project_id == project.project_id)
        .count()
    )

    return ProjectOut(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status,
        is_active=project.is_active,
        person_in_charge_id=project.person_in_charge_id,
        person_in_charge_name=project.person_in_charge.name if project.person_in_charge else None,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        member_count=member_count,
        task_count=task_count,
    )


@router.put(
    "/{project_id}/status",
    response_model=ProjectOut,
    dependencies=[Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))],
)
def update_project_status(
    project_id: int,
    payload: ProjectStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Activate/deactivate a project (is_active flag).

    Only Admin/HR can toggle project active status.
    """
    _assert_current_in_scope(db, current_user, scope)
    project = _ensure_project_exists(db, project_id, scope=scope)

    project.is_active = payload.is_active
    db.commit()
    db.refresh(project)
    action = "activated" if payload.is_active else "deactivated"
    _notify_project_members(
        db,
        project=project,
        actor=current_user,
        notification_type="Project Status Changed",
        title="Project Status Changed",
        message=f"{current_user.name} {action} project '{project.name}'.",
        scope=scope,
    )

    member_count = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.project_id, ProjectMember.is_active.is_(True))
        .count()
    )

    task_count = (
        db.query(Task)
        .filter(Task.project_id == project.project_id)
        .count()
    )

    return ProjectOut(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status,
        is_active=project.is_active,
        person_in_charge_id=project.person_in_charge_id,
        person_in_charge_name=project.person_in_charge.name if project.person_in_charge else None,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        member_count=member_count,
        task_count=task_count,
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))],
)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Delete a project.

    Only Admin/HR can delete projects.
    """
    _assert_current_in_scope(db, current_user, scope)
    project = _ensure_project_exists(db, project_id, scope=scope)
    _create_project_notifications(
        db,
        recipients=_active_project_members(
            db,
            project.project_id,
            scope=scope,
            exclude_user_id=current_user.user_id,
        ),
        project_id=None,
        notification_type="Project Deleted",
        title="Project Deleted",
        message=f"{current_user.name} deleted project '{project.name}'.",
    )

    db.delete(project)
    db.commit()

    return None


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER))],
)
def add_project_member(
    project_id: int,
    payload: ProjectMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Add a member to a project.

    - Admin/HR (PIC roles): can manage any project members.
    - Manager: can manage members only for their own projects and must have
      at least one department assigned (supports comma-separated departments).
    """
    _assert_current_in_scope(db, current_user, scope)
    project = _ensure_project_exists(db, project_id, scope=scope)

    user = _get_user_in_scope(db, payload.user_id, scope)
    if not user and current_user.role == RoleEnum.ADMIN and payload.user_id == current_user.user_id:
        # Admin access is assignment-based; allow adding self in selected tenant.
        user = current_user
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or inactive")

    # Managers: enforce department configuration, project ownership, and department match
    if current_user.role == RoleEnum.MANAGER:
        manager_depts = set(department_tokens_lower(getattr(current_user, "department", None)))
        if not manager_depts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Manager must have at least one department assigned to manage project members.",
            )

        # Manager can manage only members of their own project
        membership = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.user_id,
                ProjectMember.is_active.is_(True),
            )
            .first()
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers can manage members only for their own projects.",
            )

        # Manager can add only users from their own department(s)
        target_depts = set(department_tokens_lower(getattr(user, "department", None)))
        if not target_depts or not (manager_depts & target_depts):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers can manage members only from their own department(s).",
            )

    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.project_id, ProjectMember.user_id == payload.user_id)
        .first()
    )

    if member:
        # Reactivate + update role
        member.is_active = True
        member.removed_at = None
        member.role = payload.role
    else:
        member = ProjectMember(
            project_id=project.project_id,
            user_id=payload.user_id,
            role=payload.role,
            added_by=current_user.user_id,
        )
        db.add(member)

    db.commit()
    db.refresh(member)
    _create_project_notifications(
        db,
        recipients=[user],
        project_id=project.project_id,
        notification_type="Project Member Added",
        title="Added To Project",
        message=f"{current_user.name} added you to project '{project.name}' as {member.role}.",
    )

    return ProjectMemberOut(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        user_name=user.name,
        user_role=user.role.value if hasattr(user.role, "value") else str(user.role),
        project_role=member.role,
        is_active=member.is_active,
        added_at=member.added_at,
    )


@router.get(
    "/{project_id}/members",
    response_model=List[ProjectMemberOut],
    # Allow all roles that can belong to projects to view members:
    # Admin, HR, Manager, Team Lead, Employee
    dependencies=[Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER, RoleEnum.TEAM_LEAD, RoleEnum.EMPLOYEE))],
)
def list_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    List active members for a project.

    - Admin/HR: can list members of any project.
    - Manager/TeamLead/Employee: can list members only for projects where they are active members.
    """
    _assert_current_in_scope(db, current_user, scope)
    project = _ensure_project_exists(db, project_id, scope=scope)

    # Non-Admin/HR roles (Manager, Team Lead, Employee) must be active members of the project
    if current_user.role not in (RoleEnum.ADMIN, RoleEnum.HR):
        membership = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.user_id,
                ProjectMember.is_active.is_(True),
            )
            .first()
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can view members only for projects where you are a member.",
            )

    members = (
        db.query(ProjectMember, User)
        .join(User, ProjectMember.user_id == User.user_id)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.is_active.is_(True),
            *_user_scope_filters(scope),
        )
        .order_by(User.name.asc())
        .all()
    )

    results: List[ProjectMemberOut] = []
    for member, user in members:
        results.append(
            ProjectMemberOut(
                id=member.id,
                project_id=member.project_id,
                user_id=member.user_id,
                user_name=user.name,
                user_role=user.role.value if hasattr(user.role, "value") else str(user.role),
                project_role=member.role,
                is_active=member.is_active,
                added_at=member.added_at,
            )
        )

    return results


@router.post(
    "/{project_id}/members/bulk",
    response_model=List[ProjectMemberOut],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER))],
)
def add_project_members_bulk(
    project_id: int,
    payload: ProjectMembersBulkAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Bulk add members to a project.

    - Reactivates existing members (updates role).
    - Creates new members where needed.
    - Single role applied to all provided user IDs.
    """
    _assert_current_in_scope(db, current_user, scope)
    project = _ensure_project_exists(db, project_id, scope=scope)

    # Managers: enforce department configuration + project ownership
    if current_user.role == RoleEnum.MANAGER:
        manager_depts = set(department_tokens_lower(getattr(current_user, "department", None)))
        if not manager_depts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Manager must have at least one department assigned to manage project members.",
            )

        membership = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.user_id,
                ProjectMember.is_active.is_(True),
            )
            .first()
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers can manage members only for their own projects.",
            )

    # Deduplicate IDs
    user_ids = list({uid for uid in payload.user_ids if uid is not None})

    # Load users and validate they exist and are active
    users = (
        db.query(User)
        .filter(User.user_id.in_(user_ids), User.is_active.is_(True), *_user_scope_filters(scope))
        .all()
    )
    found_ids = {u.user_id for u in users}
    if current_user.role == RoleEnum.ADMIN and current_user.user_id in user_ids:
        found_ids.add(current_user.user_id)
    missing = [uid for uid in user_ids if uid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User(s) not found or inactive for user_id(s): {missing}",
        )

    # Preload existing member records
    existing_members = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.project_id, ProjectMember.user_id.in_(user_ids))
        .all()
    )
    members_by_user_id = {m.user_id: m for m in existing_members}

    created_or_updated: list[ProjectMember] = []

    for user in users:
        # Managers can add only users from their own department(s)
        if current_user.role == RoleEnum.MANAGER:
            target_depts = set(department_tokens_lower(getattr(user, "department", None)))
            if not target_depts or not (manager_depts & target_depts):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Managers can manage members only from their own department(s).",
                )

        member = members_by_user_id.get(user.user_id)
        if member:
            # Reactivate and update role
            member.is_active = True
            member.removed_at = None
            member.role = payload.role
        else:
            member = ProjectMember(
                project_id=project.project_id,
                user_id=user.user_id,
                role=payload.role,
                added_by=current_user.user_id,
            )
            db.add(member)
        created_or_updated.append((member, user))

    db.commit()

    # Refresh members
    for member, _ in created_or_updated:
        db.refresh(member)

    _create_project_notifications(
        db,
        recipients=users,
        project_id=project.project_id,
        notification_type="Project Members Added",
        title="Added To Project",
        message=f"{current_user.name} added you to project '{project.name}' as {payload.role}.",
    )

    return [
        ProjectMemberOut(
            id=member.id,
            project_id=member.project_id,
            user_id=member.user_id,
            user_name=user.name,
            user_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            project_role=member.role,
            is_active=member.is_active,
            added_at=member.added_at,
        )
        for member, user in created_or_updated
    ]

@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER))],
)
def remove_project_member(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Remove (deactivate) a project member.

    - Admin/HR (PIC roles): can manage any project members.
    - Manager: can manage members only for their own projects and must have
      at least one department assigned (supports comma-separated departments) and
      only for users in their own department(s).
    """
    _assert_current_in_scope(db, current_user, scope)
    project = _ensure_project_exists(db, project_id, scope=scope)

    # Managers: enforce department configuration + project ownership
    if current_user.role == RoleEnum.MANAGER:
        manager_depts = set(department_tokens_lower(getattr(current_user, "department", None)))
        if not manager_depts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Manager must have at least one department assigned to manage project members.",
            )

        membership = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.user_id,
                ProjectMember.is_active.is_(True),
            )
            .first()
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers can manage members only for their own projects.",
            )

    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id, ProjectMember.is_active.is_(True))
        .first()
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project member not found")

    # Managers can remove only users from their own department(s)
    if current_user.role == RoleEnum.MANAGER:
        user = _get_user_in_scope(db, user_id, scope)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or inactive")

        target_depts = set(department_tokens_lower(getattr(user, "department", None)))
        if not target_depts or not (manager_depts & target_depts):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers can manage members only from their own department(s).",
            )

    # Do not allow removing the PIC record via this endpoint
    if member.role == "pic":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the PIC from the project. Change PIC or archive project instead.",
        )

    removed_user = _get_user_in_scope(db, user_id, scope)
    if removed_user:
        _create_project_notifications(
            db,
            recipients=[removed_user],
            project_id=project_id,
            notification_type="Project Member Removed",
            title="Removed From Project",
            message=f"{current_user.name} removed you from project '{project.name}'.",
        )

    member.is_active = False
    member.removed_at = now_ist()

    db.commit()
    return None



