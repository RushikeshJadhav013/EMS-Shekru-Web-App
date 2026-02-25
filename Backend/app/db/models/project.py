from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Project(Base):
    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    status = Column(String(50), nullable=False, default="planned")  # planned, in_progress, completed, archived

    person_in_charge_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    person_in_charge = relationship("User", foreign_keys=[person_in_charge_id])
    created_by_user = relationship("User", foreign_keys=[created_by])
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project")

