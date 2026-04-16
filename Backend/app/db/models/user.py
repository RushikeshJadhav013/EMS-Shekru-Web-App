from sqlalchemy import Column, Integer, String, Enum, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.enums import RoleEnum
from app.utils.timezone import now_ist


class User(Base):
    __tablename__ = "users"

    # Primary Key
    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    employee_id = Column(String(500), unique=True, index=True)

    # Basic Info
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(Enum(RoleEnum), default=RoleEnum.EMPLOYEE)

    # Optional Info
    department = Column(String(255), nullable=True)
    designation = Column(String(255), nullable=True)
    # Make gender mandatory with a sane default ("other") to avoid NULLs
    gender = Column(String(50), nullable=False, default="other")
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    manager_id = Column(Integer, nullable=True)  # ✅ Added: Reporting manager user ID

    # PAN, Aadhaar, Shift, Employee Type
    pan_card = Column(String(20), nullable=True)
    aadhar_card = Column(String(20), nullable=True)
    shift_type = Column(String(50), nullable=True)
    employee_type = Column(String(50), nullable=True)  # ✅ Added: contract or permanent

    # Dates
    joining_date = Column(DateTime, default=now_ist)
    resignation_date = Column(DateTime, nullable=True)

    # Profile & status
    profile_photo = Column(String(1024), nullable=True)
    is_active = Column(Boolean, default=True)  # Active/Deactivate status
    is_email_verified = Column(Boolean, default=False)  # Email verification status for salary documents

    # Timestamps
    created_at = Column(DateTime, default=now_ist)

    # Relationships
    attendances = relationship("Attendance", back_populates="user", cascade="all, delete-orphan")
    leaves = relationship("Leave", back_populates="user", cascade="all, delete-orphan")
    assigned_tasks = relationship("Task", back_populates="assigned_to_user", foreign_keys="Task.assigned_to")
    created_tasks = relationship("Task", back_populates="assigned_by_user", foreign_keys="Task.assigned_by")
    leave_notifications = relationship("LeaveNotification", back_populates="user", cascade="all, delete-orphan")
    task_history_entries = relationship("TaskHistory", back_populates="user", cascade="all, delete-orphan")
    task_comments = relationship("TaskComment", back_populates="user", cascade="all, delete-orphan")
    task_notifications = relationship("TaskNotification", back_populates="user", cascade="all, delete-orphan")
    shift_assignments = relationship(
        "ShiftAssignment",
        foreign_keys="ShiftAssignment.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    shift_notifications = relationship("ShiftNotification", back_populates="user", cascade="all, delete-orphan")
    salary_notifications = relationship("SalaryNotification", back_populates="user", cascade="all, delete-orphan")
    wfh_notifications = relationship("WFHNotification", back_populates="user", cascade="all, delete-orphan")

    # Chat-related relationships
    created_chat_sessions = relationship(
        "ChatSession",
        back_populates="created_by",
        cascade="all, delete-orphan",
    )
    chat_memberships = relationship(
        "ChatMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Meeting-related relationships
    created_meetings = relationship(
        "Meeting",
        back_populates="created_by",
        foreign_keys="Meeting.created_by_id",
        cascade="all, delete-orphan",
    )
    meeting_participations = relationship(
        "MeetingParticipant",
        back_populates="user",
        cascade="all, delete-orphan",
    )
