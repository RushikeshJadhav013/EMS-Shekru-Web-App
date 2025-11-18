from sqlalchemy import Column, Integer, String, Time, Boolean, DateTime, ForeignKey, Date, Text, func
from sqlalchemy.orm import relationship
from app.db.database import Base


class Shift(Base):
    __tablename__ = "shifts"

    shift_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)  # e.g., "Morning Shift", "Evening Shift", "Night Shift"
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    department = Column(String(255), nullable=True)  # NULL for global shifts, or specific department
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    assignments = relationship("ShiftAssignment", back_populates="shift", cascade="all, delete-orphan")


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"

    assignment_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    shift_id = Column(Integer, ForeignKey("shifts.shift_id", ondelete="CASCADE"), nullable=False)
    assignment_date = Column(Date, nullable=False)  # Date for which the shift is assigned
    assigned_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)  # Manager who assigned
    notes = Column(String(500), nullable=True)  # Optional notes about the assignment
    is_reassigned = Column(Boolean, default=False, nullable=False)  # True if reassigned from another shift
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="shift_assignments")
    shift = relationship("Shift", back_populates="assignments")
    assigned_by_user = relationship("User", foreign_keys=[assigned_by])
    notifications = relationship("ShiftNotification", back_populates="shift_assignment", cascade="all, delete-orphan")


class ShiftNotification(Base):
    __tablename__ = "shift_notifications"

    notification_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    shift_assignment_id = Column(Integer, ForeignKey("shift_assignments.assignment_id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(100), nullable=False)  # "shift_assigned", "shift_updated", "shift_reassigned"
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="shift_notifications")
    shift_assignment = relationship("ShiftAssignment", back_populates="notifications")

