from sqlalchemy import Column, Integer, String, Date, DateTime, func, Boolean, Text
from app.db.database import Base


class CompanyHoliday(Base):
    __tablename__ = "company_holidays"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=True)
    is_recurring = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DeptWeekOffRule(Base):
    """
    Stores weekly off days for a department as a comma-separated list of weekday names.
    Example: 'Saturday,Sunday'
    """
    __tablename__ = "dept_week_off_rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    department = Column(String(255), nullable=False, index=True)
    days = Column(String(255), nullable=False)  # comma-separated weekday names
    created_by = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


