import json
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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
from app.dependencies import get_current_user
from app.utils.timezone import now_ist

from app.schemas.task_schema import (
    TaskBulkCreate,
    BulkTaskUpdate,
    TaskCreate,
    TaskHistoryOut,
    TaskNotificationOut,
    TaskOut,
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


def _validate_project_exists(db: Session, project_id: int | None) -> None:
    if not project_id:
        return
    exists = db.query(Project.project_id).filter(Project.project_id == project_id).first()
    if not exists:
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
def assign_task(task: TaskCreate, db: Session = Depends(get_db), user = Depends(get_current_user)):
    # Fetch assignee user
    assignee = db.query(User).filter(User.user_id == task.assigned_to).first()
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

    _validate_project_exists(db, task.project_id)

    t = create_task(
        db,
        task.title,
        task.description or "",
        user.user_id,
        task.assigned_to,
        task.due_date,
        task.priority or "Medium",
        project_id=task.project_id,
    )
    # Ensure assignee is added as a project member when task is linked to a project
    _ensure_project_member(db, t.project_id, t.assigned_to, user.user_id)
    return TaskOut(
        task_id=t.task_id,
        title=t.title,
        description=t.description,
        status=t.status,
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
    assignees = db.query(User).filter(User.user_id.in_(assignee_ids)).all()
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
                detail=f"Cannot assign task to same or higher role (assignee_id={assignee.user_id})",
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

    _validate_project_exists(db, payload.project_id)

    # All validations passed; create tasks
    created_tasks: list[Task] = []
    for assignee in validated_assignees:
        t = create_task(
            db,
            payload.title,
            payload.description or "",
            user.user_id,
            assignee.user_id,
            payload.due_date,
            payload.priority or "Medium",
            project_id=payload.project_id,
        )
        # Ensure each assignee is added as a project member when task is linked to a project
        _ensure_project_member(db, t.project_id, t.assigned_to, user.user_id)
        created_tasks.append(t)

    # Return list of TaskOut
    return [
        TaskOut(
            task_id=t.task_id,
            title=t.title,
            description=t.description,
            status=t.status,
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

@router.get("/", response_model=list[TaskOut])
def my_tasks(db: Session = Depends(get_db), user = Depends(get_current_user)):
    tasks = list_tasks(db, user.user_id)
    # Enrich tasks with human-readable names for assigned_by and assigned_to
    return [
        TaskOut(
            task_id=t.task_id,
            title=t.title,
            description=t.description,
            status=t.status,
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
def update_status(task_id: int, status: TaskStatus, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Fetch current task
    existing_task = db.query(Task).filter(Task.task_id == task_id).first()
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

    task = update_task_status(db, task_id, status, user.user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskOut(
        task_id=task.task_id,
        title=task.title,
        description=task.description,
        status=task.status,
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
):
    """
    Bulk update multiple tasks. Assigned users are preserved; this endpoint no longer
    creates additional tasks or assignees.
    """
    updates = payload.updates.model_dump(exclude_unset=True)
    if not updates:
        # Nothing to update; return current tasks
        tasks = db.query(Task).filter(Task.task_id.in_(payload.task_ids)).all()
        return [
            TaskOut(
                task_id=t.task_id,
                title=t.title,
                description=t.description,
                status=t.status,
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
        existing: Task | None = db.query(Task).filter(Task.task_id == task_id).first()
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

        updated = update_task(db, task_id=task_id, updates=updates, updated_by=user.user_id)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Task not found (task_id={task_id})")
        updated_tasks.append(updated)

    return [
        TaskOut(
            task_id=t.task_id,
            title=t.title,
            description=t.description,
            status=t.status,
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
):
    existing: Task | None = db.query(Task).filter(Task.task_id == task_id).first()
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
        assignee = db.query(User).filter(User.user_id == new_assignee_id).first()
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

    updated = update_task(db, task_id=task_id, updates=updates, updated_by=user.user_id)
    if not updated:
        raise HTTPException(status_code=400, detail="Task update failed")
    return TaskOut(
        task_id=updated.task_id,
        title=updated.title,
        description=updated.description,
        status=updated.status,
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
def delete_my_task(task_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    existing = db.query(Task).filter(Task.task_id == task_id).first()
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

    task = delete_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}


@router.post("/{task_id}/pass", response_model=TaskOut)
def pass_task_route(
    task_id: int,
    payload: TaskPassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.task_id == task_id).first()
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

    new_assignee = db.query(User).filter(User.user_id == payload.new_assignee_id).first()
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
    )

    return TaskOut(
        task_id=updated_task.task_id,
        title=updated_task.title,
        description=updated_task.description,
        status=updated_task.status,
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
):
    task = db.query(Task).filter(Task.task_id == task_id).first()
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

    entries = get_task_history(db, task_id)
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
):
    notifications = list_task_notifications(db, current_user.user_id)
    return [_serialize_task_notification(notification) for notification in notifications]


@router.put("/notifications/{notification_id}/read", response_model=TaskNotificationOut)
def mark_task_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = mark_task_notification_as_read(
        db,
        notification_id=notification_id,
        user_id=current_user.user_id,
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return _serialize_task_notification(notification)


@router.get("/deadline-warnings/{user_id}")
def get_deadline_warnings(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get tasks with upcoming or overdue deadlines for a user"""
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized to view this user's tasks")
    
    today = date.today()
    three_days_from_now = today + timedelta(days=3)
    
    # Get tasks assigned to user with deadlines within 3 days or overdue
    tasks = db.query(Task).filter(
        Task.assigned_to == user_id,
        Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
        Task.due_date.isnot(None),
        Task.due_date <= three_days_from_now
    ).all()
    
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
