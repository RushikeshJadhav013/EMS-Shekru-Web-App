from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.database import get_db
from app.crud.task_crud import create_task, list_tasks, update_task_status, delete_task
from app.dependencies import get_current_user, require_roles

from app.schemas.task_schema import TaskCreate, TaskOut
from app.enums import TaskStatus

router = APIRouter(prefix="/tasks", tags=["Tasks"])

@router.post("/", response_model=TaskOut)
def assign_task(task: TaskCreate, db: Session = Depends(get_db), user = Depends(get_current_user)):
    return create_task(db, user.user_id, task.assigned_to, task.title, task.description, task.due_date)

@router.get("/", response_model=list[TaskOut])
def my_tasks(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return list_tasks(db, user.user_id)

@router.put("/{task_id}/status", response_model=TaskOut)
def update_status(task_id: int, status: TaskStatus, db: Session = Depends(get_db), user = Depends(get_current_user)):
    task = update_task_status(db, task_id, status)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.delete("/{task_id}")
def delete_my_task(task_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    task = delete_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}
