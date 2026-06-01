import json
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, aliased

from app.db.database import get_db
from app.crud.task_crud import (
    create_task,
    create_task_notification,
    delete_task,
    get_task_history,
    list_task_notifications,
    list_tasks,
    mark_task_notification_as_read,
    pass_task,
    update_task,
    update_task_status,
)
from app.dependencies import get_current_user, get_tenant_scope
from app.utils.timezone import now_ist

from app.schemas.task_schema import (
    TaskBulkCreate,
    BulkTaskUpdate,
    TaskCreate,
    TaskHistoryOut,
    TaskNotificationOut,
    TaskOut,
    TaskOutWithoutProject,
    TaskPassRequest,
    TaskUpdate,
)
from app.enums import RoleEnum, TaskStatus
from app.db.models.task import Task, TaskHistory
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.project_member import ProjectMember
from app.utils.department_utils import department_tokens_lower

router = APIRouter(prefix="/tasks", tags=["Tasks"])

# -------------------------------------------------------------------
# Tenant scoping helpers
# -------------------------------------------------------------------
def _user_scope_filters(scope: dict, user_alias=User) -> list:
    clauses = [user_alias.company_id == scope["company_id"]]
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        clauses.append(user_alias.branch_id == branch_id)
    return clauses


def _get_user_in_scope(db: Session, user_id: int, scope: dict) -> User | None:
    return (
        db.query(User)
        .filter(User.user_id == user_id, User.is_active.is_(True), *_user_scope_filters(scope))
        .first()
    )


def _assert_current_in_scope(db: Session, current_user: User, scope: dict) -> None:
    """Admins are scoped via assignments in get_tenant_scope, not users.company_id."""
    if current_user.role == RoleEnum.ADMIN:
        return
    if _get_user_in_scope(db, int(current_user.user_id), scope) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current user is outside selected tenant scope",
        )


def _task_in_scope_query(db: Session, scope: dict):
    q = db.query(Task).filter(Task.company_id == int(scope["company_id"]))
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        creator = aliased(User)
        assignee = aliased(User)
        q = (
            q.outerjoin(creator, Task.assigned_by == creator.user_id)
            .outerjoin(assignee, Task.assigned_to == assignee.user_id)
            .filter(creator.branch_id == int(branch_id), assignee.branch_id == int(branch_id))
        )
    return q


def _ensure_project_member(db: Session, project_id: int | None, user_id: int | None, added_by: int | None) -> None:
    """
    Ensure a user is an active member of a project when a task is linked to that project.
    - If member exists but inactive: reactivate.
    - If member doesn't exist: create with role 'member'.
    """
    if not project_id or not user_id:
        return

    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )

    if member:
        if not member.is_active:
            member.is_active = True
            member.removed_at = None
    else:
        member = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role="member",
            added_by=added_by,
        )
        db.add(member)

    db.commit()


def _validate_project_exists(db: Session, project_id: int | None, scope: dict | None = None) -> None:
    if not project_id:
        return
    q = db.query(Project).filter(Project.project_id == project_id)
    if scope is not None:
        q = q.filter(Project.company_id == int(scope["company_id"]))
        branch_id = scope.get("branch_id")
        if branch_id is not None:
            q = q.filter(Project.branch_id == int(branch_id))
    project = q.first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found for project_id={project_id}",
        )
def _serialize_task_notification(notification: TaskNotificationOut | Task):
    raw_details = getattr(notification, "pass_details", None)
    parsed_details = None
    if raw_details:
        try:
            parsed_details = json.loads(raw_details)
        except (json.JSONDecodeError, TypeError):
            parsed_details = {"raw": raw_details}

    return TaskNotificationOut(
        notification_id=notification.notification_id,
        user_id=notification.user_id,
        task_id=notification.task_id,
        notification_type=notification.notification_type,
        title=notification.title,
        message=notification.message,
        pass_details=parsed_details,
        is_read=notification.is_read,
        created_at=notification.created_at,
    )


@router.post("/", response_model=TaskOut)
def assign_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, user, scope)
    # Fetch assignee user
    assignee = _get_user_in_scope(db, int(task.assigned_to), scope)
    if not assignee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")

    # Allow self-assignment always
    if task.assigned_to != user.user_id:
        # Enforce role hierarchy: cannot assign to users with higher role
        try:
            assigner_index = ROLE_HIERARCHY.index(user.role)
            assignee_index = ROLE_HIERARCHY.index(assignee.role)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role configuration")

        # Disallow assigning to users with the same or higher role (except self-assignment)
        if assignee_index <= assigner_index:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign task to same or higher role")

        # Manager-specific department restriction
        if user.role == RoleEnum.MANAGER and user.department:
            manager_tokens = set(department_tokens_lower(user.department))
            assignee_tokens = set(department_tokens_lower(assignee.department))
            if not manager_tokens.intersection(assignee_tokens):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers can assign tasks only to users in their departments")

    _validate_project_exists(db, task.project_id, scope)

    try:
        t = create_task(
            db,
            task.title,
            task.description or "",
            user.user_id,
            task.assigned_to,
            start_date=datetime.combine(task.start_date, datetime.min.time()) if task.start_date else None,
            due_date=datetime.combine(task.due_date, datetime.min.time()) if task.due_date else None,
            priority=task.priority or "Medium",
            project_id=task.project_id,
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Ensure assignee is added as a project member when task is linked to a project
    _ensure_project_member(db, t.project_id, t.assigned_to, user.user_id)
    return TaskOut(
        task_id=t.task_id,
        company_id=int(t.company_id),
        title=t.title,
        description=t.description,
        status=t.status,
        start_date=t.start_date.date() if t.start_date else None,
        due_date=t.due_date.date() if t.due_date else None,
        priority=t.priority,
        assigned_to=t.assigned_to,
        assigned_by=t.assigned_by,
        project_id=t.project_id,
        created_at=t.created_at,
        last_passed_by=t.last_passed_by,
        last_passed_to=t.last_passed_to,
        last_pass_note=t.last_pass_note,
        last_passed_at=t.last_passed_at,
        assigned_to_name=t.assigned_to_user.name if t.assigned_to_user else None,
        assigned_by_name=t.assigned_by_user.name if t.assigned_by_user else None,
        assigned_by_role=t.assigned_by_user.role if t.assigned_by_user else None,
        assigned_to_role=t.assigned_to_user.role if t.assigned_to_user else None,
    )


@router.post("/bulk", response_model=list[TaskOut])
def assign_tasks_bulk(
    payload: TaskBulkCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Assign the same task to multiple users.

    This reuses the existing single-task `create_task` logic for each assignee.
    Role hierarchy and department rules are applied per assignee, just like
    in the single `assign_task` endpoint.
    """
    # Remove duplicates and ensure at least one ID (schema already enforces this)
    assignee_ids = list({uid for uid in payload.assigned_to_ids if uid is not None})

    # Pre-load all assignees and validate existence
    _assert_current_in_scope(db, user, scope)
    assignees = (
        db.query(User)
        .filter(User.user_id.in_(assignee_ids), *_user_scope_filters(scope))
        .all()
    )
    found_ids = {u.user_id for u in assignees}
    missing = [uid for uid in assignee_ids if uid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignee(s) not found for user_id(s): {missing}",
        )

    # Apply the same role/department checks as in `assign_task` for each assignee
    validated_assignees: list[User] = []
    for assignee in assignees:
        if assignee.user_id == user.user_id:
            # Self-assignment always allowed
            validated_assignees.append(assignee)
            continue

        try:
            assigner_index = ROLE_HIERARCHY.index(user.role)
            assignee_index = ROLE_HIERARCHY.index(assignee.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role configuration",
            )

        if assignee_index <= assigner_index:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot asstcsign task to same or higher role (assignee_id={assignee.user_id})",
            )

        if user.role == RoleEnum.MANAGER and user.department:
            manager_tokens = set(department_tokens_lower(user.department))
            assignee_tokens = set(department_tokens_lower(assignee.department))
            if not manager_tokens.intersection(assignee_tokens):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Managers can assign tasks only to users in their departments (assignee_id={assignee.user_id})",
                )

        validated_assignees.append(assignee)

    _validate_project_exists(db, payload.project_id, scope)

    # All validations passed; create tasks
    created_tasks: list[Task] = []
    for assignee in validated_assignees:
        try:
            t = create_task(
                db,
                payload.title,
                payload.description or "",
                user.user_id,
                assignee.user_id,
                start_date=datetime.combine(payload.start_date, datetime.min.time()) if payload.start_date else None,
                due_date=datetime.combine(payload.due_date, datetime.min.time()) if payload.due_date else None,
                priority=payload.priority or "Medium",
                project_id=payload.project_id,
                company_id=scope["company_id"],
                branch_id=scope.get("branch_id"),
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        # Ensure each assignee is added as a project member when task is linked to a project
        _ensure_project_member(db, t.project_id, t.assigned_to, user.user_id)
        created_tasks.append(t)

    # Return list of TaskOut
    return [
        TaskOut(
            task_id=t.task_id,
            company_id=int(t.company_id),
            title=t.title,
            description=t.description,
            status=t.status,
            start_date=t.start_date.date() if t.start_date else None,
            due_date=t.due_date.date() if t.due_date else None,
            priority=t.priority,
            assigned_to=t.assigned_to,
            assigned_by=t.assigned_by,
            project_id=t.project_id,
            created_at=t.created_at,
            last_passed_by=t.last_passed_by,
            last_passed_to=t.last_passed_to,
            last_pass_note=t.last_pass_note,
            last_passed_at=t.last_passed_at,
            assigned_to_name=t.assigned_to_user.name if t.assigned_to_user else None,
            assigned_by_name=t.assigned_by_user.name if t.assigned_by_user else None,
            assigned_by_role=t.assigned_by_user.role if t.assigned_by_user else None,
            assigned_to_role=t.assigned_to_user.role if t.assigned_to_user else None,
        )
        for t in created_tasks
    ]

@router.get("/", response_model=list[TaskOutWithoutProject])
def my_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    List standalone tasks for the current user (non-project tasks only).
    Project-linked tasks are exposed via a separate endpoint to avoid duplication in the UI.
    """
    """
    List standalone (non-project) tasks visible to the current user.
    Visibility rules:
    - ADMIN: all non-project tasks except tasks involving other Admins only.
    - HR: all non-project tasks except tasks created by Admins and assigned to other HRs.
    - MANAGER: all non-project tasks related to their department(s).
    - TEAM_LEAD / EMPLOYEE: only tasks where they are creator/assignee/participant (existing behavior).
    """
    # Non-project tasks only
    TaskCreator = aliased(User)
    TaskAssignee = aliased(User)

    if user.role == RoleEnum.ADMIN:
        # Admins can see all non-project tasks except tasks where Admins are involved
        # and the current admin is not part of the task.
        q = (
            db.query(Task)
            .outerjoin(TaskCreator, Task.assigned_by == TaskCreator.user_id)
            .outerjoin(TaskAssignee, Task.assigned_to == TaskAssignee.user_id)
            .filter(Task.project_id.is_(None))
            .filter(Task.company_id == int(scope["company_id"]))
        )

        # Exclude tasks involving other admins only (creator or assignee is ADMIN)
        q = q.filter(
            ~(
                (
                    (TaskCreator.role == RoleEnum.ADMIN)
                    | (TaskAssignee.role == RoleEnum.ADMIN)
                )
                & (Task.assigned_by != user.user_id)
                & (Task.assigned_to != user.user_id)
            )
        )
        tasks = q.all()

    elif user.role == RoleEnum.HR:
        # HR can see all non-project tasks except those created by Admins and
        # assigned to other HRs (i.e. HRs other than themselves).
        q = (
            db.query(Task)
            .outerjoin(TaskCreator, Task.assigned_by == TaskCreator.user_id)
            .outerjoin(TaskAssignee, Task.assigned_to == TaskAssignee.user_id)
            .filter(Task.project_id.is_(None))
            .filter(Task.company_id == int(scope["company_id"]))
        )

        q = q.filter(
            ~(
                (TaskCreator.role == RoleEnum.ADMIN)
                & (TaskAssignee.role == RoleEnum.HR)
                & (Task.assigned_to != user.user_id)
            )
        )
        tasks = q.all()

    elif user.role == RoleEnum.MANAGER:
        # Managers: see non-project tasks related to their department(s).
        manager_tokens = set(department_tokens_lower(getattr(user, "department", None)))
        if not manager_tokens:
            tasks = []
        else:
            tasks = (
                db.query(Task)
                .outerjoin(TaskCreator, Task.assigned_by == TaskCreator.user_id)
                .outerjoin(TaskAssignee, Task.assigned_to == TaskAssignee.user_id)
                .filter(Task.project_id.is_(None))
                .filter(Task.company_id == int(scope["company_id"]))
                .all()
            )

            def in_manager_dept(u: User | None) -> bool:
                if not u or not getattr(u, "department", None):
                    return False
                tokens = set(department_tokens_lower(u.department))
                return bool(manager_tokens & tokens)

            tasks = [
                t
                for t in tasks
                if in_manager_dept(t.assigned_by_user) or in_manager_dept(t.assigned_to_user)
            ]

    else:
        # Team Leads / Employees: keep existing per-user visibility via list_tasks
        tasks = list_tasks(
            db,
            user.user_id,
            project_only=False,
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )

    return [
        TaskOut(
            task_id=t.task_id,
            company_id=int(t.company_id),
            title=t.title,
            description=t.description,
            status=t.status,
            start_date=t.start_date.date() if t.start_date else None,
            due_date=t.due_date.date() if t.due_date else None,
            priority=t.priority,
            assigned_to=t.assigned_to,
            assigned_by=t.assigned_by,
            created_at=t.created_at,
            last_passed_by=t.last_passed_by,
            last_passed_to=t.last_passed_to,
            last_pass_note=t.last_pass_note,
            last_passed_at=t.last_passed_at,
            assigned_to_name=t.assigned_to_user.name if t.assigned_to_user else None,
            assigned_by_name=t.assigned_by_user.name if t.assigned_by_user else None,
            assigned_by_role=t.assigned_by_user.role if t.assigned_by_user else None,
            assigned_to_role=t.assigned_to_user.role if t.assigned_to_user else None,
        )
        for t in tasks
    ]


@router.get("/projects/{project_id}", response_model=list[TaskOut])
def project_tasks(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    List project-linked tasks for a given project that are visible to the current user.

    Project access:
    - Admin/HR: can access any project.
    - Manager/TeamLead/Employee: must be active members of the project.

    Task visibility inside the project:
    - ADMIN: all tasks in the project except tasks involving only other Admins.
    - HR: all tasks in the project except tasks created by Admins and assigned to other HRs.
    - MANAGER: all tasks in the project related to their department(s).
    - TEAM_LEAD / EMPLOYEE: only tasks where they are creator/assignee/participant.
    """
    # Ensure project exists in tenant scope
    project = (
        db.query(Project)
        .filter(
            Project.project_id == project_id,
            Project.company_id == int(scope["company_id"]),
        )
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Ensure user has access to this project
    if user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        is_member = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.user_id,
                ProjectMember.is_active.is_(True),
            )
            .first()
        )
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this project",
            )

    TaskCreator = aliased(User)
    TaskAssignee = aliased(User)

    if user.role == RoleEnum.ADMIN:
        # Admins: all tasks in the project except tasks where only other Admins are involved
        q = (
            db.query(Task)
            .outerjoin(TaskCreator, Task.assigned_by == TaskCreator.user_id)
            .outerjoin(TaskAssignee, Task.assigned_to == TaskAssignee.user_id)
            .filter(Task.project_id == project_id)
            .filter(Task.company_id == int(scope["company_id"]))
        )

        q = q.filter(
            ~(
                (
                    (TaskCreator.role == RoleEnum.ADMIN)
                    | (TaskAssignee.role == RoleEnum.ADMIN)
                )
                & (Task.assigned_by != user.user_id)
                & (Task.assigned_to != user.user_id)
            )
        )
        tasks = q.all()

    elif user.role == RoleEnum.HR:
        # HR: all tasks in the project except tasks created by Admins and
        # assigned to other HRs (not themselves).
        q = (
            db.query(Task)
            .outerjoin(TaskCreator, Task.assigned_by == TaskCreator.user_id)
            .outerjoin(TaskAssignee, Task.assigned_to == TaskAssignee.user_id)
            .filter(Task.project_id == project_id)
            .filter(Task.company_id == int(scope["company_id"]))
        )

        q = q.filter(
            ~(
                (TaskCreator.role == RoleEnum.ADMIN)
                & (TaskAssignee.role == RoleEnum.HR)
                & (Task.assigned_to != user.user_id)
            )
        )
        tasks = q.all()

    elif user.role == RoleEnum.MANAGER:
        # Managers: see project tasks related to their department(s)
        manager_tokens = set(department_tokens_lower(getattr(user, "department", None)))
        if not manager_tokens:
            tasks = []
        else:
            tasks = (
                db.query(Task)
                .outerjoin(TaskCreator, Task.assigned_by == TaskCreator.user_id)
                .outerjoin(TaskAssignee, Task.assigned_to == TaskAssignee.user_id)
                .filter(Task.project_id == project_id)
                .filter(Task.company_id == int(scope["company_id"]))
                .all()
            )

            def in_manager_dept(u: User | None) -> bool:
                if not u or not getattr(u, "department", None):
                    return False
                tokens = set(department_tokens_lower(u.department))
                return bool(manager_tokens & tokens)

            tasks = [
                t
                for t in tasks
                if in_manager_dept(t.assigned_by_user) or in_manager_dept(t.assigned_to_user)
            ]

    else:
        # Team Leads / Employees: per-user, per-project visibility via list_tasks
        tasks = list_tasks(
            db,
            user.user_id,
            project_only=True,
            project_id=project_id,
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )

    return [
        TaskOut(
            task_id=t.task_id,
            company_id=int(t.company_id),
            title=t.title,
            description=t.description,
            status=t.status,
            start_date=t.start_date.date() if t.start_date else None,
            due_date=t.due_date.date() if t.due_date else None,
            priority=t.priority,
            assigned_to=t.assigned_to,
            assigned_by=t.assigned_by,
            project_id=t.project_id,
            created_at=t.created_at,
            last_passed_by=t.last_passed_by,
            last_passed_to=t.last_passed_to,
            last_pass_note=t.last_pass_note,
            last_passed_at=t.last_passed_at,
            assigned_to_name=t.assigned_to_user.name if t.assigned_to_user else None,
            assigned_by_name=t.assigned_by_user.name if t.assigned_by_user else None,
            assigned_by_role=t.assigned_by_user.role if t.assigned_by_user else None,
            assigned_to_role=t.assigned_to_user.role if t.assigned_to_user else None,
        )
        for t in tasks
    ]

ROLE_HIERARCHY = [
    RoleEnum.ADMIN,
    RoleEnum.HR,
    RoleEnum.MANAGER,
    RoleEnum.TEAM_LEAD,
    RoleEnum.EMPLOYEE,
]


def _ensure_can_pass(current_user: User, new_assignee: User) -> None:
    try:
        current_index = ROLE_HIERARCHY.index(current_user.role)
        target_index = ROLE_HIERARCHY.index(new_assignee.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role configuration")

    if target_index <= current_index:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot pass task to same or higher role")

    if current_user.role != RoleEnum.ADMIN:
        if current_user.department and new_assignee.department:
            curr_tokens = set(department_tokens_lower(current_user.department))
            new_tokens = set(department_tokens_lower(new_assignee.department))
            # If no intersection, not allowed
            if not curr_tokens.intersection(new_tokens):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot pass tasks outside your department")


@router.put("/{task_id}/status", response_model=TaskOut)
def update_status(
    task_id: int,
    status: TaskStatus,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    # Fetch current task
    existing_task = _task_in_scope_query(db, scope).filter(Task.task_id == task_id).first()
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Permission checks: Admin, assignee, creator, or higher role than assignee
    if user.role != RoleEnum.ADMIN and user.user_id not in (existing_task.assigned_to, existing_task.assigned_by):
        assignee = db.query(User).filter(User.user_id == existing_task.assigned_to).first()
        if not assignee:
            raise HTTPException(status_code=404, detail="Assignee not found")
        try:
            current_index = ROLE_HIERARCHY.index(user.role)
            assignee_index = ROLE_HIERARCHY.index(assignee.role)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role configuration")

        if current_index >= assignee_index:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this task's status")

    task = update_task_status(
        db,
        task_id,
        status,
        user.user_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskOut(
        task_id=task.task_id,
        company_id=int(task.company_id),
        title=task.title,
        description=task.description,
        status=task.status,
        start_date=task.start_date.date() if task.start_date else None,
        due_date=task.due_date.date() if task.due_date else None,
        priority=task.priority,
        assigned_to=task.assigned_to,
        assigned_by=task.assigned_by,
        project_id=task.project_id,
        created_at=task.created_at,
        last_passed_by=task.last_passed_by,
        last_passed_to=task.last_passed_to,
        last_pass_note=task.last_pass_note,
        last_passed_at=task.last_passed_at,
        assigned_to_name=task.assigned_to_user.name if task.assigned_to_user else None,
        assigned_by_name=task.assigned_by_user.name if task.assigned_by_user else None,
        assigned_by_role=task.assigned_by_user.role if task.assigned_by_user else None,
        assigned_to_role=task.assigned_to_user.role if task.assigned_to_user else None,
    )


@router.put("/bulk", response_model=list[TaskOut])
def update_tasks_bulk(
    payload: BulkTaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    Bulk update multiple tasks. Assigned users are preserved; this endpoint no longer
    creates additional tasks or assignees.
    """
    updates = payload.updates.model_dump(exclude_unset=True)
    if not updates:
        # Nothing to update; return current tasks
        tasks = _task_in_scope_query(db, scope).filter(Task.task_id.in_(payload.task_ids)).all()
        return [
            TaskOut(
                task_id=t.task_id,
                company_id=int(t.company_id),
                title=t.title,
                description=t.description,
                status=t.status,
                start_date=t.start_date.date() if t.start_date else None,
                due_date=t.due_date.date() if t.due_date else None,
                priority=t.priority,
                assigned_to=t.assigned_to,
                assigned_by=t.assigned_by,
                project_id=t.project_id,
                created_at=t.created_at,
                last_passed_by=t.last_passed_by,
                last_passed_to=t.last_passed_to,
                last_pass_note=t.last_pass_note,
                last_passed_at=t.last_passed_at,
                assigned_to_name=t.assigned_to_user.name if t.assigned_to_user else None,
                assigned_by_name=t.assigned_by_user.name if t.assigned_by_user else None,
                assigned_by_role=t.assigned_by_user.role if t.assigned_by_user else None,
                assigned_to_role=t.assigned_to_user.role if t.assigned_to_user else None,
            )
            for t in tasks
        ]

    updated_tasks: list[Task] = []
    for task_id in payload.task_ids:
        existing: Task | None = _task_in_scope_query(db, scope).filter(Task.task_id == task_id).first()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Task not found (task_id={task_id})")

        # Reuse permission logic from `edit_task`
        if user.role != RoleEnum.ADMIN and existing.assigned_by != user.user_id:
            creator = db.query(User).filter(User.user_id == existing.assigned_by).first()
            if not creator:
                raise HTTPException(
                    status_code=403,
                    detail=f"Only the task creator or higher roles can edit this task (task_id={task_id})",
                )
            try:
                current_index = ROLE_HIERARCHY.index(user.role)
                creator_index = ROLE_HIERARCHY.index(creator.role)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid role configuration",
                )
            if current_index >= creator_index:
                raise HTTPException(
                    status_code=403,
                    detail=f"Only the task creator or higher roles can edit this task (task_id={task_id})",
                )

        updated = update_task(
            db,
            task_id=task_id,
            updates=updates,
            updated_by=user.user_id,
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Task not found (task_id={task_id})")
        updated_tasks.append(updated)

    return [
        TaskOut(
            task_id=t.task_id,
            company_id=int(t.company_id),
            title=t.title,
            description=t.description,
            status=t.status,
            start_date=t.start_date.date() if t.start_date else None,
            due_date=t.due_date.date() if t.due_date else None,
            priority=t.priority,
            assigned_to=t.assigned_to,
            assigned_by=t.assigned_by,
            project_id=t.project_id,
            created_at=t.created_at,
            last_passed_by=t.last_passed_by,
            last_passed_to=t.last_passed_to,
            last_pass_note=t.last_pass_note,
            last_passed_at=t.last_passed_at,
            assigned_to_name=t.assigned_to_user.name if t.assigned_to_user else None,
            assigned_by_name=t.assigned_by_user.name if t.assigned_by_user else None,
            assigned_by_role=t.assigned_by_user.role if t.assigned_by_user else None,
            assigned_to_role=t.assigned_to_user.role if t.assigned_to_user else None,
        )
        for t in updated_tasks
    ]


@router.put("/{task_id}", response_model=TaskOut)
def edit_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    existing: Task | None = _task_in_scope_query(db, scope).filter(Task.task_id == task_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    # Allow edit if Admin, creator, or user with higher role than creator
    if user.role != RoleEnum.ADMIN and existing.assigned_by != user.user_id:
        creator = db.query(User).filter(User.user_id == existing.assigned_by).first()
        if not creator:
            raise HTTPException(status_code=403, detail="Only the task creator or higher roles can edit this task")
        try:
            current_index = ROLE_HIERARCHY.index(user.role)
            creator_index = ROLE_HIERARCHY.index(creator.role)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role configuration")
        if current_index >= creator_index:
            raise HTTPException(status_code=403, detail="Only the task creator or higher roles can edit this task")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return existing
    # If the update includes changing the assignee, enforce role hierarchy rules
    if "assigned_to" in updates:
        new_assignee_id = updates["assigned_to"]
        assignee = _get_user_in_scope(db, int(new_assignee_id), scope)
        if not assignee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")

        # Allow self-assignment always
        if new_assignee_id != user.user_id:
            try:
                editor_index = ROLE_HIERARCHY.index(user.role)
                assignee_index = ROLE_HIERARCHY.index(assignee.role)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role configuration")

            # Disallow assigning to same or higher role
            if assignee_index <= editor_index:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign task to same or higher role")

            # Manager-specific department restriction
            if user.role == RoleEnum.MANAGER and user.department:
                manager_tokens = set(department_tokens_lower(user.department))
                assignee_tokens = set(department_tokens_lower(assignee.department))
                if not manager_tokens.intersection(assignee_tokens):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers can assign tasks only to users in their departments")

    updated = update_task(
        db,
        task_id=task_id,
        updates=updates,
        updated_by=user.user_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    if not updated:
        raise HTTPException(status_code=400, detail="Task update failed")
    return TaskOut(
        task_id=updated.task_id,
        company_id=int(updated.company_id),
        title=updated.title,
        description=updated.description,
        status=updated.status,
        start_date=updated.start_date.date() if updated.start_date else None,
        due_date=updated.due_date.date() if updated.due_date else None,
        priority=updated.priority,
        assigned_to=updated.assigned_to,
        assigned_by=updated.assigned_by,
        project_id=updated.project_id,
        created_at=updated.created_at,
        last_passed_by=updated.last_passed_by,
        last_passed_to=updated.last_passed_to,
        last_pass_note=updated.last_pass_note,
        last_passed_at=updated.last_passed_at,
        assigned_to_name=updated.assigned_to_user.name if updated.assigned_to_user else None,
        assigned_by_name=updated.assigned_by_user.name if updated.assigned_by_user else None,
        assigned_by_role=updated.assigned_by_user.role if updated.assigned_by_user else None,
        assigned_to_role=updated.assigned_to_user.role if updated.assigned_to_user else None,
    )

@router.delete("/{task_id}")
def delete_my_task(
    task_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    existing = _task_in_scope_query(db, scope).filter(Task.task_id == task_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    # Allow delete if Admin, creator, or user with higher role than creator
    if user.role != RoleEnum.ADMIN and existing.assigned_by != user.user_id:
        creator = db.query(User).filter(User.user_id == existing.assigned_by).first()
        if not creator:
            raise HTTPException(status_code=403, detail="Only the task creator or higher roles can delete this task")
        try:
            current_index = ROLE_HIERARCHY.index(user.role)
            creator_index = ROLE_HIERARCHY.index(creator.role)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role configuration")
        if current_index >= creator_index:
            raise HTTPException(status_code=403, detail="Only the task creator or higher roles can delete this task")

    task = delete_task(
        db,
        task_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}


@router.post("/{task_id}/pass", response_model=TaskOut)
def pass_task_route(
    task_id: int,
    payload: TaskPassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    task = _task_in_scope_query(db, scope).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Prevent passing completed or cancelled tasks
    if task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Cannot pass a task with status '{task.status}'. Only pending or in-progress tasks can be passed."
        )

    if current_user.role != RoleEnum.ADMIN and task.assigned_to != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the current assignee can pass this task")

    new_assignee = _get_user_in_scope(db, int(payload.new_assignee_id), scope)
    if not new_assignee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="New assignee not found")

    _ensure_can_pass(current_user, new_assignee)

    previous_assignee = task.assigned_to

    updated_task = pass_task(
        db,
        task_id=task_id,
        current_user_id=current_user.user_id,
        new_assignee_id=payload.new_assignee_id,
        note=payload.note,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )

    if not updated_task:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to pass task")

    new_assignee_name = new_assignee.name if new_assignee else None

    pass_details = {
        "from": previous_assignee,
        "from_name": current_user.name,
        "to": payload.new_assignee_id,
        "to_name": new_assignee_name,
        "note": payload.note,
    }

    title = "Task Passed"
    message = f"{current_user.name} passed task '{task.title}' to you."

    create_task_notification(
        db,
        task_id=task_id,
        recipient_id=payload.new_assignee_id,
        title=title,
        message=message,
        pass_details=pass_details,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )

    return TaskOut(
        task_id=updated_task.task_id,
        company_id=int(updated_task.company_id),
        title=updated_task.title,
        description=updated_task.description,
        status=updated_task.status,
        start_date=updated_task.start_date.date() if updated_task.start_date else None,
        due_date=updated_task.due_date.date() if updated_task.due_date else None,
        priority=updated_task.priority,
        assigned_to=updated_task.assigned_to,
        assigned_by=updated_task.assigned_by,
        project_id=updated_task.project_id,
        created_at=updated_task.created_at,
        last_passed_by=updated_task.last_passed_by,
        last_passed_to=updated_task.last_passed_to,
        last_pass_note=updated_task.last_pass_note,
        last_passed_at=updated_task.last_passed_at,
        assigned_to_name=updated_task.assigned_to_user.name if updated_task.assigned_to_user else None,
        assigned_by_name=updated_task.assigned_by_user.name if updated_task.assigned_by_user else None,
        assigned_by_role=updated_task.assigned_by_user.role if updated_task.assigned_by_user else None,
        assigned_to_role=updated_task.assigned_to_user.role if updated_task.assigned_to_user else None,
    )


@router.get("/{task_id}/history", response_model=list[TaskHistoryOut])
def task_history(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    task = _task_in_scope_query(db, scope).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if (
        current_user.role != RoleEnum.ADMIN
        and task.assigned_to != current_user.user_id
        and task.assigned_by != current_user.user_id
    ):
        participated = (
            db.query(TaskHistory)
            .filter(
                TaskHistory.task_id == task_id,
                TaskHistory.user_id == current_user.user_id,
            )
            .first()
        )
        if not participated:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this task history")

    entries = get_task_history(
        db,
        task_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    history: list[TaskHistoryOut] = []
    for entry in entries:
        details = None
        if entry.details:
            try:
                details = json.loads(entry.details)
            except json.JSONDecodeError:
                details = {"raw": entry.details}
        history.append(
            TaskHistoryOut(
                id=entry.id,
                task_id=entry.task_id,
                user_id=entry.user_id,
                action=entry.action,
                details=details,
                created_at=entry.created_at,
            )
        )
    return history


@router.get("/notifications", response_model=list[TaskNotificationOut])
def task_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    notifications = list_task_notifications(
        db,
        current_user.user_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    return [_serialize_task_notification(notification) for notification in notifications]


@router.put("/notifications/{notification_id}/read", response_model=TaskNotificationOut)
def mark_task_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    notification = mark_task_notification_as_read(
        db,
        notification_id=notification_id,
        user_id=current_user.user_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return _serialize_task_notification(notification)


@router.get("/deadline-warnings/{user_id}")
def get_deadline_warnings(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Get tasks with upcoming or overdue deadlines for a user"""
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized to view this user's tasks")
    
    today = date.today()
    three_days_from_now = today + timedelta(days=3)
    
    if _get_user_in_scope(db, int(user_id), scope) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in selected tenant scope")

    # Get tasks assigned to user with deadlines within 3 days or overdue
    tasks = (
        db.query(Task)
        .filter(
            Task.assigned_to == user_id,
            Task.company_id == int(scope["company_id"]),
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            Task.due_date.isnot(None),
            Task.due_date <= three_days_from_now,
        )
        .all()
    )
    
    warnings = []
    for task in tasks:
        if task.due_date:
            # Convert datetime to date for comparison
            task_due_date = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
            days_until_deadline = (task_due_date - today).days
            
            if days_until_deadline < 0:
                warning_type = "overdue"
                message = f"Task '{task.title}' is {abs(days_until_deadline)} day(s) overdue"
            elif days_until_deadline == 0:
                warning_type = "due_today"
                message = f"Task '{task.title}' is due today"
            else:
                warning_type = "upcoming"
                message = f"Task '{task.title}' is due in {days_until_deadline} day(s)"
            
            warnings.append({
                "task_id": task.task_id,
                "title": task.title,
                "due_date": task.due_date.isoformat(),
                "status": task.status,
                "priority": task.priority,
                "warning_type": warning_type,
                "message": message,
                "days_until_deadline": days_until_deadline
            })
    
    return {"warnings": warnings}
