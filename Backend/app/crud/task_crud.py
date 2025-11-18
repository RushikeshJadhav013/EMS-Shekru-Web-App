import json
from datetime import date, datetime
from typing import Optional

from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session

from app.db.models.task import Task, TaskHistory
from app.db.models.notification import TaskNotification
from app.db.models.user import User
from app.enums import TaskAction, TaskStatus


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
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    return entry


def create_task(db: Session, title: str, description: str, assigned_by: int, assigned_to: int, due_date: Optional[datetime]):
    _ensure_task_pass_columns(db)
    task = Task(
        title=title,
        description=description,
        assigned_by=assigned_by,
        assigned_to=assigned_to,
        due_date=due_date,
        status=TaskStatus.PENDING,
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

def list_tasks(db: Session, user_id: int):
    _ensure_task_pass_columns(db)
    return (
        db.query(Task)
        .outerjoin(TaskHistory, TaskHistory.task_id == Task.task_id)
        .filter(
            or_(
                Task.assigned_to == user_id,
                Task.assigned_by == user_id,
                TaskHistory.user_id == user_id,
            )
        )
        .distinct()
        .all()
    )

def update_task_status(db: Session, task_id: int, status: TaskStatus, updated_by: int):
    task = db.query(Task).filter(Task.task_id == task_id).first()
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
):
    task = db.query(Task).filter(Task.task_id == task_id).first()
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

def delete_task(db: Session, task_id: int):
    task = db.query(Task).filter(Task.task_id == task_id).first()
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
) -> Optional[Task]:
    _ensure_task_pass_columns(db)
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        return None

    previous_assignee = task.assigned_to
    task.assigned_to = new_assignee_id
    task.last_passed_by = current_user_id
    task.last_passed_to = new_assignee_id
    task.last_pass_note = note
    task.last_passed_at = datetime.utcnow()

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
        },
    )

    db.commit()
    db.refresh(task)
    return task


def get_task_history(db: Session, task_id: int) -> list[TaskHistory]:
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
) -> TaskNotification:
    _ensure_task_notification_table(db)
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


def list_task_notifications(db: Session, user_id: int) -> list[TaskNotification]:
    _ensure_task_notification_table(db)
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
) -> Optional[TaskNotification]:
    _ensure_task_notification_table(db)
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
