from sqlalchemy import Column, Integer, DateTime, String, ForeignKey, Numeric, func
from sqlalchemy.orm import relationship
from app.db.database import Base

class Leave(Base):
    __tablename__ = "leaves"
    leave_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"))
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    reason = Column(String(255))
    status = Column(String(50), default="Pending")
    leave_type = Column(String(50), default="annual")
    # 1.0 = full day; 0.5 = half day (unpaid before/after lunch)
    duration_days = Column(Numeric(3, 1), nullable=False, default=1.0)
    # before_lunch | after_lunch when duration_days == 0.5 and leave_type == unpaid
    leave_session = Column(String(20), nullable=True)

    user = relationship("User", back_populates="leaves")
    notifications = relationship("LeaveNotification", back_populates="leave", cascade="all, delete-orphan")
