from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, Float, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


class Attendance(Base):
    __tablename__ = "attendances"

    attendance_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"))
    check_in = Column(DateTime, nullable=False)
    check_out = Column(DateTime, nullable=True)
    total_hours = Column(Float, default=0.0)  # Total hours worked today
    gps_location = Column(String(255), nullable=True)
    selfie = Column(String(1024), nullable=True)
    work_summary = Column(Text, nullable=True)
    work_report = Column(String(1024), nullable=True)
    work_location = Column(String(50), default='office')  # 'office' or 'work_from_home'
    task_deadline_reason = Column(Text, nullable=True)  # Reason for incomplete tasks on deadline

    user = relationship("User", back_populates="attendances")
