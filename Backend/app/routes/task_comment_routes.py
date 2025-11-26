from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.db.database import get_db
from app.db.models.task import Task
from app.db.models.task_comment import TaskComment
from app.db.models.user import User
from app.dependencies import get_current_user
from pydantic import BaseModel


router = APIRouter(prefix="/tasks", tags=["Task Comments"])


# Schemas
class TaskCommentCreate(BaseModel):
    comment: str


class TaskCommentOut(BaseModel):
    id: int
    task_id: int
    user_id: int
    user_name: str
    user_role: str
    comment: str
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


@router.get("/{task_id}/comments", response_model=List[TaskCommentOut])
def get_task_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all comments for a task.
    Only accessible by task assignee, assigned_to, or users involved in task passing.
    """
    # Get the task
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check if user has access to this task
    user_id = current_user.user_id
    has_access = (
        task.assigned_by == user_id or
        task.assigned_to == user_id or
        task.last_passed_by == user_id or
        task.last_passed_to == user_id
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to view comments for this task"
        )
    
    # Get all comments with user information
    comments = (
        db.query(TaskComment)
        .filter(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc())
        .all()
    )
    
    # Format response with user information
    result = []
    for comment in comments:
        user = db.query(User).filter(User.user_id == comment.user_id).first()
        result.append(TaskCommentOut(
            id=comment.id,
            task_id=comment.task_id,
            user_id=comment.user_id,
            user_name=user.name if user else "Unknown User",
            user_role=user.role.value if user and hasattr(user.role, 'value') else str(user.role) if user else "Unknown",
            comment=comment.comment,
            created_at=comment.created_at,
            updated_at=comment.updated_at
        ))
    
    return result


@router.post("/{task_id}/comments", response_model=TaskCommentOut, status_code=status.HTTP_201_CREATED)
def create_task_comment(
    task_id: int,
    comment_data: TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a comment to a task.
    Only accessible by task assignee, assigned_to, or users involved in task passing.
    """
    # Get the task
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check if user has access to comment on this task
    user_id = current_user.user_id
    has_access = (
        task.assigned_by == user_id or
        task.assigned_to == user_id or
        task.last_passed_by == user_id or
        task.last_passed_to == user_id
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to comment on this task"
        )
    
    # Create the comment
    new_comment = TaskComment(
        task_id=task_id,
        user_id=user_id,
        comment=comment_data.comment.strip()
    )
    
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    
    # Return with user information
    return TaskCommentOut(
        id=new_comment.id,
        task_id=new_comment.task_id,
        user_id=new_comment.user_id,
        user_name=current_user.name,
        user_role=current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role),
        comment=new_comment.comment,
        created_at=new_comment.created_at,
        updated_at=new_comment.updated_at
    )


@router.delete("/{task_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_comment(
    task_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a comment. Only the comment author can delete their own comment.
    """
    comment = db.query(TaskComment).filter(
        TaskComment.id == comment_id,
        TaskComment.task_id == task_id
    ).first()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    # Only the comment author can delete it
    if comment.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments"
        )
    
    db.delete(comment)
    db.commit()
    
    return None
