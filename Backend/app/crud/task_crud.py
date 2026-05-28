import json
from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, inspect, or_, text
from sqlalchemy.orm import Session, aliased

from app.db.models.task import Task, TaskHistory
from app.db.models.notification import TaskNotification
from app.db.models.user import User
from app.enums import TaskAction, TaskStatus
from app.utils.timezone import now_ist


_TASK_PASS_COLUMNS_READY = False
_TASK_NOTIFICATION_TABLE_READY = False


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _ensure_task_pass_columns(db: Session) -> None:
    global _TASK_PASS_COLUMNS_READY
    if _TASK_PASS_COLUMNS_READY:
        return

    bind = db.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("tasks")}

    statements: list[str] = []

    if "last_passed_by" not in columns:
        statements.append("ALTER TABLE tasks ADD COLUMN last_passed_by INTEGER")
    if "last_passed_to" not in columns:
        statements.append("ALTER TABLE tasks ADD COLUMN last_passed_to INTEGER")
    if "last_pass_note" not in columns:
        statements.append("ALTER TABLE tasks ADD COLUMN last_pass_note TEXT")
    if "last_passed_at" not in columns:
        statements.append("ALTER TABLE tasks ADD COLUMN last_passed_at TIMESTAMP")
    if "project_id" not in columns:
        statements.append("ALTER TABLE tasks ADD COLUMN project_id INTEGER")

    for statement in statements:
        db.execute(text(statement))

    if statements:
        db.commit()

    _TASK_PASS_COLUMNS_READY = True


def _ensure_task_notification_table(db: Session) -> None:
    global _TASK_NOTIFICATION_TABLE_READY
    if _TASK_NOTIFICATION_TABLE_READY:
        return

    bind = db.get_bind()
    TaskNotification.__table__.create(bind, checkfirst=True)

    _TASK_NOTIFICATION_TABLE_READY = True


def _record_history(
    db: Session,
    *,
    task_id: int,
    user_id: int,
    action: TaskAction,
    details: Optional[dict] = None,
) -> TaskHistory:
    entry = TaskHistory(
        task_id=task_id,
        user_id=user_id,
        action=action.value,
        details=json.dumps(details or {}, default=_json_default),
        created_at=now_ist(),
    )
    db.add(entry)
    return entry


def _user_scope_clauses(user_model, company_id: int | None, branch_id: int | None) -> list:
    clauses = []
    if company_id is not None:
        clauses.append(user_model.company_id == company_id)
    if branch_id is not None:
        clauses.append(user_model.branch_id == branch_id)
    return clauses


def _get_user_in_scope(
    db: Session,
    *,
    user_id: int,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[User]:
    q = db.query(User).filter(User.user_id == user_id)
    for clause in _user_scope_clauses(User, company_id, branch_id):
        q = q.filter(clause)
    return q.first()


def _apply_task_scope(
    query,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
):
    if company_id is None and branch_id is None:
        return query

    creator = aliased(User)
    assignee = aliased(User)
    query = query.outerjoin(creator, Task.assigned_by == creator.user_id).outerjoin(
        assignee, Task.assigned_to == assignee.user_id
    )
    creator_clauses = _user_scope_clauses(creator, company_id, branch_id)
    assignee_clauses = _user_scope_clauses(assignee, company_id, branch_id)
    if creator_clauses:
        query = query.filter(and_(*creator_clauses))
    if assignee_clauses:
        query = query.filter(and_(*assignee_clauses))
    return query


def create_task(
    db: Session,
    title: str,
    description: str,
    assigned_by: int,
    assigned_to: int,
    *,
    start_date: Optional[datetime] = None,
    due_date: Optional[datetime] = None,
    priority: Optional[str] = "Medium",
    project_id: Optional[int] = None,
    company_id: int | None = None,
    branch_id: int | None = None,
):
    _ensure_task_pass_columns(db)
    if (company_id is not None or branch_id is not None) and (
        _get_user_in_scope(db, user_id=assigned_by, company_id=company_id, branch_id=branch_id) is None
        or _get_user_in_scope(db, user_id=assigned_to, company_id=company_id, branch_id=branch_id) is None
    ):
        raise ValueError("Assigner/assignee not in tenant scope")

    task = Task(
        title=title,
        description=description,
        assigned_by=assigned_by,
        assigned_to=assigned_to,
        start_date=start_date,
        due_date=due_date,
        status=TaskStatus.PENDING,
        priority=priority or "Medium",
        project_id=project_id,
    )
    db.add(task)
    db.flush()

    _record_history(
        db,
        task_id=task.task_id,
        user_id=assigned_by,
        action=TaskAction.CREATED,
        details={
            "assigned_to": assigned_to,
            "status": TaskStatus.PENDING.value,
        },
    )

    if assigned_to and assigned_to != assigned_by:
        create_task_notification(
            db,
            task_id=task.task_id,
            recipient_id=assigned_to,
            title="New Task Assigned",
            message=f"You have been assigned a new task: '{task.title}'.",
            pass_details={
                "from": assigned_by,
                "to": assigned_to,
            },
        )

    db.commit()
    db.refresh(task)
    return task

def list_tasks(
    db: Session,
    user_id: int,
    *,
    project_only: bool | None = None,
    project_id: int | None = None,
    company_id: int | None = None,
    branch_id: int | None = None,
):
    """
    List tasks visible to a user.
    - project_only=None (default): include both project and non-project tasks.
    - project_only=False: only tasks with no project (project_id is NULL).
    - project_only=True: only tasks linked to a project; if project_id is provided,
      further restrict to that project.
    """
    _ensure_task_pass_columns(db)

    query = (
        db.query(Task)
        .outerjoin(TaskHistory, TaskHistory.task_id == Task.task_id)
        .filter(
            or_(
                Task.assigned_to == user_id,
                Task.assigned_by == user_id,
                TaskHistory.user_id == user_id,
            )
        )
    )
    query = _apply_task_scope(query, company_id=company_id, branch_id=branch_id)

    if project_only is True:
        query = query.filter(Task.project_id.isnot(None))
        if project_id is not None:
            query = query.filter(Task.project_id == project_id)
    elif project_only is False:
        query = query.filter(Task.project_id.is_(None))

    return query.distinct().all()

def update_task_status(
    db: Session,
    task_id: int,
    status: TaskStatus,
    updated_by: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
):
    task_query = db.query(Task).filter(Task.task_id == task_id)
    task_query = _apply_task_scope(task_query, company_id=company_id, branch_id=branch_id)
    task = task_query.first()
    if task:
        previous_status = task.status
        task.status = status
        db.commit()
        db.refresh(task)

        _record_history(
            db,
            task_id=task_id,
            user_id=updated_by,
            action=TaskAction.STATUS_CHANGED,
            details={
                "from": previous_status,
                "to": status.value,
            },
        )
        db.commit()
    return task

def update_task(
    db: Session,
    *,
    task_id: int,
    updates: dict,
    updated_by: int,
    company_id: int | None = None,
    branch_id: int | None = None,
):
    task_query = db.query(Task).filter(Task.task_id == task_id)
    task_query = _apply_task_scope(task_query, company_id=company_id, branch_id=branch_id)
    task = task_query.first()
    if not task:
        return None

    original_values = {}
    for field, value in updates.items():
        original_values[field] = getattr(task, field)
        setattr(task, field, value)

    db.commit()
    db.refresh(task)

    if updates:
        _record_history(
            db,
            task_id=task_id,
            user_id=updated_by,
            action=TaskAction.UPDATED,
            details={
                "changes": {
                    field: {
                        "from": original_values[field],
                        "to": updates[field],
                    }
                    for field in updates
                }
            },
        )
        db.commit()

    return task

def delete_task(
    db: Session,
    task_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
):
    task_query = db.query(Task).filter(Task.task_id == task_id)
    task_query = _apply_task_scope(task_query, company_id=company_id, branch_id=branch_id)
    task = task_query.first()
    if task:
        db.delete(task)
        db.commit()
    return task


def pass_task(
    db: Session,
    *,
    task_id: int,
    current_user_id: int,
    new_assignee_id: int,
    note: Optional[str] = None,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[Task]:
    _ensure_task_pass_columns(db)
    task_query = db.query(Task).filter(Task.task_id == task_id)
    task_query = _apply_task_scope(task_query, company_id=company_id, branch_id=branch_id)
    task = task_query.first()
    if not task:
        return None

    if (company_id is not None or branch_id is not None) and _get_user_in_scope(
        db, user_id=new_assignee_id, company_id=company_id, branch_id=branch_id
    ) is None:
        return None

    previous_assignee = task.assigned_to
    previous_status = task.status
    
    # Update task assignment
    task.assigned_to = new_assignee_id
    task.last_passed_by = current_user_id
    task.last_passed_to = new_assignee_id
    task.last_pass_note = note
    task.last_passed_at = now_ist()
    
    # Reset status to Pending when task is passed to a new assignee
    # This ensures the new assignee starts fresh with the task
    task.status = TaskStatus.PENDING

    new_assignee = db.query(User).filter(User.user_id == new_assignee_id).first()
    _record_history(
        db,
        task_id=task_id,
        user_id=current_user_id,
        action=TaskAction.PASSED,
        details={
            "from": previous_assignee,
            "to": new_assignee_id,
            "to_name": new_assignee.name if new_assignee else None,
            "note": note,
            "previous_status": previous_status,
            "new_status": TaskStatus.PENDING.value,
        },
    )

    db.commit()
    db.refresh(task)
    return task


def get_task_history(
    db: Session,
    task_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> list[TaskHistory]:
    if company_id is not None or branch_id is not None:
        task_query = db.query(Task).filter(Task.task_id == task_id)
        task_query = _apply_task_scope(task_query, company_id=company_id, branch_id=branch_id)
        if task_query.first() is None:
            return []
    return (
        db.query(TaskHistory)
        .filter(TaskHistory.task_id == task_id)
        .order_by(TaskHistory.created_at.desc())
        .all()
    )


def create_task_notification(
    db: Session,
    *,
    task_id: int,
    recipient_id: int,
    title: str,
    message: str,
    pass_details: Optional[dict] = None,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> TaskNotification:
    _ensure_task_notification_table(db)
    if (company_id is not None or branch_id is not None) and _get_user_in_scope(
        db, user_id=recipient_id, company_id=company_id, branch_id=branch_id
    ) is None:
        raise ValueError("Notification recipient not in tenant scope")
    notification = TaskNotification(
        user_id=recipient_id,
        task_id=task_id,
        title=title,
        message=message,
        pass_details=json.dumps(pass_details or {}, default=_json_default) if pass_details else None,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def list_task_notifications(
    db: Session,
    user_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> list[TaskNotification]:
    _ensure_task_notification_table(db)
    if (company_id is not None or branch_id is not None) and _get_user_in_scope(
        db, user_id=user_id, company_id=company_id, branch_id=branch_id
    ) is None:
        return []
    return (
        db.query(TaskNotification)
        .filter(TaskNotification.user_id == user_id)
        .order_by(TaskNotification.created_at.desc())
        .all()
    )


def mark_task_notification_as_read(
    db: Session,
    *,
    notification_id: int,
    user_id: int,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[TaskNotification]:
    _ensure_task_notification_table(db)
    if (company_id is not None or branch_id is not None) and _get_user_in_scope(
        db, user_id=user_id, company_id=company_id, branch_id=branch_id
    ) is None:
        return None
    notification = (
        db.query(TaskNotification)
        .filter(
            TaskNotification.notification_id == notification_id,
            TaskNotification.user_id == user_id,
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
