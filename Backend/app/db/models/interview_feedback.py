from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.utils.timezone import now_ist


def get_now_ist() -> datetime:
    """Get current time in IST (naive) for database storage."""
    return now_ist()


class InterviewFeedback(Base):
    __tablename__ = "interview_feedbacks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    interview_id = Column(Integer, ForeignKey("interviews.interview_id", ondelete="CASCADE"), nullable=False)
    panel_member_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)

    feedback_summary = Column(Text, nullable=False)
    rating = Column(Integer, nullable=True)  # 1-5 rating
    strengths = Column(Text, nullable=True)
    weaknesses = Column(Text, nullable=True)
    recommendation = Column(String(50), nullable=True)  # hire, reject, hold, etc.

    created_at = Column(DateTime, default=get_now_ist, nullable=False)
    # Only updated when the row is modified; stays NULL on initial insert
    updated_at = Column(DateTime, onupdate=get_now_ist)

    # Relationships
    interview = relationship("Interview", back_populates="feedbacks")
    panel_member = relationship("User")

