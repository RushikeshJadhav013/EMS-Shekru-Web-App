from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
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

    assigned_by_user = relationship("User", back_populates="created_tasks", foreign_keys="Task.assigned_by")
    assigned_to_user = relationship("User", back_populates="assigned_tasks", foreign_keys="Task.assigned_to")