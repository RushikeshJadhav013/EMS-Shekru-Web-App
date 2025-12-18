from sqlalchemy import Column, Integer, String, Time, DateTime, Boolean
from app.utils.timezone import now_ist

from app.db.database import Base


class OfficeTiming(Base):
    """Stores office hour configuration globally or per department."""

    __tablename__ = "office_timings"

    id = Column(Integer, primary_key=True, index=True)
    department = Column(String(255), nullable=True, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    check_in_grace_minutes = Column(Integer, default=0)
    check_out_grace_minutes = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    def is_global(self) -> bool:
        return self.department is None or self.department == ""
