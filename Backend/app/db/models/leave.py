from sqlalchemy import Column, Integer, DateTime, String, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.database import Base

class Leave(Base):
    __tablename__ = "leaves"
    leave_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"))
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    reason = Column(String(255))
    status = Column(String(50), default="Pending")

    user = relationship("User", back_populates="leaves")
