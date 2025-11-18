from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.database import Base


class LeaveNotification(Base):
    __tablename__ = "leave_notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    leave_id = Column(Integer, ForeignKey("leaves.leave_id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="leave_notifications")
    leave = relationship("Leave", back_populates="notifications")


class TaskNotification(Base):
    __tablename__ = "task_notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(100), default="task_pass", nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    pass_details = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="task_notifications")
    task = relationship("Task", back_populates="notifications")
