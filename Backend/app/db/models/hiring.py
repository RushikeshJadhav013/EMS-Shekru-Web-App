from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
from app.db.database import Base

class Vacancy(Base):
    __tablename__ = "vacancies"

    vacancy_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    department = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    responsibilities = Column(Text, nullable=True)
    nice_to_have_skills = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    employment_type = Column(String(50), nullable=True)  # Full-time, Part-time, Contract
    experience_required = Column(String(100), nullable=True)
    salary_range = Column(String(100), nullable=True)
    status = Column(String(50), default="open")  # open, closed, on_hold
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    closing_date = Column(DateTime(timezone=True), nullable=True)
    
    # Social media posting
    posted_on_linkedin = Column(Boolean, default=False)
    posted_on_naukri = Column(Boolean, default=False)
    posted_on_indeed = Column(Boolean, default=False)
    posted_on_other = Column(Boolean, default=False)
    social_media_links = Column(Text, nullable=True)  # JSON string of links
    
    # Relationships
    created_by_user = relationship("User", foreign_keys=[created_by])
    candidates = relationship("Candidate", back_populates="vacancy", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "candidates"

    candidate_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vacancy_id = Column(Integer, ForeignKey("vacancies.vacancy_id", ondelete="CASCADE"), nullable=False)
    
    # Personal Info
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    resume_url = Column(String(1024), nullable=True)
    
    # Application Details
    cover_letter = Column(Text, nullable=True)
    experience_years = Column(Integer, nullable=True)
    current_company = Column(String(255), nullable=True)
    current_position = Column(String(255), nullable=True)
    expected_salary = Column(String(100), nullable=True)
    notice_period = Column(String(50), nullable=True)
    
    # Status
    status = Column(String(50), default="applied")  # applied, screening, interview, shortlisted, rejected, hired
    interview_date = Column(DateTime(timezone=True), nullable=True)
    interview_notes = Column(Text, nullable=True)
    
    # Source
    source = Column(String(100), nullable=True)  # linkedin, naukri, indeed, referral, other
    
    # Timestamps
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    vacancy = relationship("Vacancy", back_populates="candidates")

