from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.enums import TaskStatus
from app.db.database import Base

class Task(Base):
    __tablename__ = "tasks"
    task_id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1024))
    assigned_by = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"))
    assigned_to = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"))
    status = Column(String(50), default=TaskStatus.PENDING)
    due_date = Column(DateTime)
    last_passed_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    last_passed_to = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    last_pass_note = Column(Text, nullable=True)
    last_passed_at = Column(DateTime, nullable=True)

    assigned_by_user = relationship("User", back_populates="created_tasks", foreign_keys="Task.assigned_by")
    assigned_to_user = relationship("User", back_populates="assigned_tasks", foreign_keys="Task.assigned_to")
    history = relationship("TaskHistory", back_populates="task", cascade="all, delete-orphan")
    notifications = relationship("TaskNotification", back_populates="task", cascade="all, delete-orphan")
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan", order_by="TaskComment.created_at")


class TaskHistory(Base):
    __tablename__ = "task_history"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"))
    action = Column(String(50))
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="history")
    user = relationship("User", back_populates="task_history_entries")