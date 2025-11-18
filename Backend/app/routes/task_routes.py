import json
from datetime import datetime

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

from app.schemas.task_schema import TaskCreate, TaskHistoryOut, TaskNotificationOut, TaskOut, TaskPassRequest, TaskUpdate
from app.enums import RoleEnum, TaskStatus
from app.db.models.task import Task, TaskHistory
from app.db.models.user import User

router = APIRouter(prefix="/tasks", tags=["Tasks"])
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
    return create_task(
        db,
        task.title,
        task.description or "",
        user.user_id,
        task.assigned_to,
        task.due_date,
    )

@router.get("/", response_model=list[TaskOut])
def my_tasks(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return list_tasks(db, user.user_id)

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
            if current_user.department != new_assignee.department:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot pass tasks outside your department")


@router.put("/{task_id}/status", response_model=TaskOut)
def update_status(task_id: int, status: TaskStatus, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = update_task_status(db, task_id, status, user.user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


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

    if user.role != RoleEnum.ADMIN and existing.assigned_by != user.user_id:
        raise HTTPException(status_code=403, detail="Only the task creator can edit this task")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return existing

    updated = update_task(db, task_id=task_id, updates=updates, updated_by=user.user_id)
    if not updated:
        raise HTTPException(status_code=400, detail="Task update failed")

    return updated

@router.delete("/{task_id}")
def delete_my_task(task_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    existing = db.query(Task).filter(Task.task_id == task_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    if user.role != RoleEnum.ADMIN and existing.assigned_by != user.user_id:
        raise HTTPException(status_code=403, detail="Only the task creator can delete this task")

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

    return updated_task


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
