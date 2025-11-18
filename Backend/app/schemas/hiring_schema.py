from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# Vacancy Schemas
class VacancyBase(BaseModel):
    title: str
    department: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    nice_to_have_skills: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    experience_required: Optional[str] = None
    salary_range: Optional[str] = None
    status: Optional[str] = "open"
    closing_date: Optional[datetime] = None

class VacancyCreate(VacancyBase):
    pass

class VacancyUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    nice_to_have_skills: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    experience_required: Optional[str] = None
    salary_range: Optional[str] = None
    status: Optional[str] = None
    closing_date: Optional[datetime] = None
    posted_on_linkedin: Optional[bool] = None
    posted_on_naukri: Optional[bool] = None
    posted_on_indeed: Optional[bool] = None
    posted_on_other: Optional[bool] = None
    social_media_links: Optional[str] = None

class VacancyOut(VacancyBase):
    vacancy_id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    posted_on_linkedin: bool
    posted_on_naukri: bool
    posted_on_indeed: bool
    posted_on_other: bool
    social_media_links: Optional[str] = None
    candidates_count: Optional[int] = 0

    model_config = {"from_attributes": True}

# Candidate Schemas
class CandidateBase(BaseModel):
    vacancy_id: int
    name: str
    email: EmailStr
    phone: Optional[str] = None
    cover_letter: Optional[str] = None
    experience_years: Optional[int] = None
    current_company: Optional[str] = None
    current_position: Optional[str] = None
    expected_salary: Optional[str] = None
    notice_period: Optional[str] = None
    source: Optional[str] = None

class CandidateCreate(CandidateBase):
    resume_url: Optional[str] = None

class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    cover_letter: Optional[str] = None
    experience_years: Optional[int] = None
    current_company: Optional[str] = None
    current_position: Optional[str] = None
    expected_salary: Optional[str] = None
    notice_period: Optional[str] = None
    status: Optional[str] = None
    interview_date: Optional[datetime] = None
    interview_notes: Optional[str] = None
    source: Optional[str] = None

class CandidateOut(CandidateBase):
    candidate_id: int
    resume_url: Optional[str] = None
    status: str
    interview_date: Optional[datetime] = None
    interview_notes: Optional[str] = None
    applied_at: datetime
    updated_at: Optional[datetime] = None
    vacancy_title: Optional[str] = None
    vacancy_department: Optional[str] = None

    model_config = {"from_attributes": True}

# Social Media Posting Schema
class SocialMediaPost(BaseModel):
    vacancy_id: int
    platforms: List[str]  # ["linkedin", "naukri", "indeed", "other"]
    links: Optional[dict] = None

