from sqlalchemy import Column, Integer, String, Text, DateTime, func, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_departments_company_code"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False, index=True)

    manager_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="active")
    employee_count = Column(Integer, nullable=True)
    location = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    manager = relationship("User", backref="managed_departments", foreign_keys=[manager_id])


