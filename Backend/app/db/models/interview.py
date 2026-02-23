from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.database import Base


class Interview(Base):
    __tablename__ = "interviews"

    interview_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.candidate_id", ondelete="CASCADE"), nullable=False)
    vacancy_id = Column(Integer, ForeignKey("vacancies.vacancy_id", ondelete="CASCADE"), nullable=False)
    scheduled_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    
    # Interview Details
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    mode = Column(String(50), nullable=True)  # onsite, remote, phone
    location = Column(String(255), nullable=True)  # meeting room / call link
    round_type = Column(String(100), nullable=True)  # HR, Technical, Managerial, etc.
    
    # Status and Feedback
    status = Column(String(50), default="scheduled")  # scheduled, completed, cancelled, no_show, rescheduled
    feedback_summary = Column(Text, nullable=True)
    rating = Column(Integer, nullable=True)  # 1-5 rating
    panel_members = Column(Text, nullable=True)  # JSON string of user_ids or names
    
    # Timestamps
    scheduled_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    candidate = relationship("Candidate", back_populates="interviews")
    vacancy = relationship("Vacancy", back_populates="interviews")
    scheduled_by_user = relationship("User", foreign_keys=[scheduled_by])
    feedbacks = relationship("InterviewFeedback", back_populates="interview", cascade="all, delete-orphan")
