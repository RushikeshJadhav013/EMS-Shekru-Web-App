from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.database import Base


class LeaveNotification(Base):
    __tablename__ = "leave_notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    leave_id = Column(Integer, ForeignKey("leaves.leave_id", ondelete="CASCADE"), nullable=True)
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


class SalaryNotification(Base):
    __tablename__ = "salary_notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(100), nullable=False)  # salary_slip, increment, annexure, offer
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="salary_notifications")


class WFHNotification(Base):
    __tablename__ = "wfh_notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    wfh_id = Column(Integer, ForeignKey("wfh_requests.wfh_id", ondelete="CASCADE"), nullable=True)
    notification_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="wfh_notifications")
    wfh_request = relationship("WFHRequest", back_populates="notifications")


class ProjectNotification(Base):
    __tablename__ = "project_notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=True)
    notification_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="project_notifications")
    project = relationship("Project", back_populates="notifications")


class MeetingNotification(Base):
    __tablename__ = "meeting_notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    # Keep notification history even if meeting row is removed.
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True)
    notification_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="meeting_notifications")
    meeting = relationship("Meeting", back_populates="notifications")


class ChatNotification(Base):
    __tablename__ = "chat_notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    chat_id = Column(String(255), ForeignKey("chat_sessions.chat_id", ondelete="CASCADE"), nullable=False)
    msg_id = Column(String(36), ForeignKey("chat_messages.msg_id", ondelete="SET NULL"), nullable=True)
    sender_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    notification_type = Column(String(100), nullable=False)  # new_message, new_file_message
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", foreign_keys=[user_id], back_populates="chat_notifications")


class CompanyHolidayNotification(Base):
    __tablename__ = "company_holiday_notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    holiday_id = Column(Integer, ForeignKey("company_holidays.id", ondelete="SET NULL"), nullable=True)
    notification_type = Column(String(100), nullable=False)  # holiday_created, holiday_deleted
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="company_holiday_notifications")
