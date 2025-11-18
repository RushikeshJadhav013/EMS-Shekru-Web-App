from sqlalchemy import Column, Integer, String, Text, DateTime, Float, func, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False, unique=True, index=True)

    manager_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="active")
    employee_count = Column(Integer, nullable=True)
    budget = Column(Float, nullable=True)
    location = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    manager = relationship("User", backref="managed_departments", foreign_keys=[manager_id])


