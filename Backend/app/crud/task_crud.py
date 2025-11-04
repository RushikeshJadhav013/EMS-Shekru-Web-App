from sqlalchemy.orm import Session
from datetime import datetime
from app.db.models.task import Task
from app.enums import TaskStatus

def create_task(db: Session, title: str, description: str, assigned_by: str, assigned_to: str, due_date: datetime):
    task = Task(title=title, description=description, assigned_by=assigned_by,
                assigned_to=assigned_to, due_date=due_date, status=TaskStatus.PENDING)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def list_tasks(db: Session, user_id: int):
    return db.query(Task).filter(Task.assigned_to == user_id).all()

def update_task_status(db: Session, task_id: int, status: TaskStatus):
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if task:
        task.status = status
        db.commit()
        db.refresh(task)
    return task

def delete_task(db: Session, task_id: int):
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
    return task
