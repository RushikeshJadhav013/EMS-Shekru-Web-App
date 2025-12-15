from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.utils.timezone import now_ist

def get_now_ist():
    """Get current time in IST (naive) for database storage"""
    return now_ist()


class TaskComment(Base):
    __tablename__ = "task_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    comment = Column(Text, nullable=True)  # Made nullable for file-only messages
    file_url = Column(String(500), nullable=True)  # Store file URL
    file_name = Column(String(255), nullable=True)  # Original file name
    file_type = Column(String(100), nullable=True)  # MIME type
    file_size = Column(Integer, nullable=True)  # File size in bytes
    created_at = Column(DateTime, default=get_now_ist, nullable=False)
    updated_at = Column(DateTime, default=get_now_ist, onupdate=get_now_ist)
    
    # Relationships
    task = relationship("Task", back_populates="comments")
    user = relationship("User", back_populates="task_comments")
