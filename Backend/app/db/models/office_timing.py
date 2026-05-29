from sqlalchemy import Column, Integer, String, Time, DateTime, Boolean, ForeignKey
from app.utils.timezone import now_ist

from app.db.database import Base


class OfficeTiming(Base):
    """Stores office hour configuration per company, optionally per department."""

    __tablename__ = "office_timings"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    department = Column(String(255), nullable=True, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    check_in_grace_minutes = Column(Integer, default=0)
    check_out_grace_minutes = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    def is_company_default(self) -> bool:
        return self.department is None or self.department == ""
