from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, Boolean, Text, func
from sqlalchemy.orm import relationship
from app.db.database import Base

class OnlineStatus(Base):
    __tablename__ = "online_status_logs"

    id = Column(Integer, primary_key=True, index=True)
    attendance_id = Column(Integer, ForeignKey("attendances.attendance_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    is_online = Column(Boolean, nullable=False)
    reason = Column(Text, nullable=True)  # Reason for going offline
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    attendance = relationship("Attendance")
    user = relationship("User")
