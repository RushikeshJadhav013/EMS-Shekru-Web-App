from sqlalchemy import Column, Integer, String, Time, DateTime, Boolean, func

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def is_global(self) -> bool:
        return self.department is None or self.department == ""
