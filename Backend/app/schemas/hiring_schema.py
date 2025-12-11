from pydantic import BaseModel, EmailStr, Field, field_validator, constr
from typing import Optional, List, Literal
from datetime import datetime, date, timedelta
import re

# Vacancy Schemas
class VacancyBase(BaseModel):
    title: constr(min_length=3, max_length=255, strip_whitespace=True) = Field(..., description="Job title (3-255 characters)")
    department: constr(min_length=2, max_length=255, strip_whitespace=True) = Field(..., description="Department name")
    description: Optional[constr(max_length=5000, strip_whitespace=True)] = Field(None, description="Job description")
    requirements: Optional[constr(max_length=3000, strip_whitespace=True)] = Field(None, description="Job requirements")
    responsibilities: Optional[constr(max_length=3000, strip_whitespace=True)] = Field(None, description="Job responsibilities")
    nice_to_have_skills: Optional[constr(max_length=1000, strip_whitespace=True)] = Field(None, description="Nice to have skills")
    location: Optional[constr(max_length=255, strip_whitespace=True)] = Field(None, description="Job location")
    employment_type: Optional[Literal['full-time', 'part-time', 'contract', 'internship', 'temporary']] = Field(None, description="Employment type")
    experience_required: Optional[constr(max_length=100, strip_whitespace=True)] = Field(None, description="Experience required")
    salary_range: Optional[constr(max_length=100, strip_whitespace=True)] = Field(None, description="Salary range")
    status: Optional[Literal['open', 'closed', 'on-hold', 'filled']] = Field("open", description="Vacancy status")
    closing_date: Optional[datetime] = Field(None, description="Application closing date")

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate job title"""
        if not v or not v.strip():
            raise ValueError('Job title cannot be empty')
        return v.strip()

    @field_validator('closing_date')
    @classmethod
    def validate_closing_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate closing date is in the future"""
        if v is not None:
            if v.date() < date.today():
                raise ValueError('Closing date cannot be in the past')
            if v.date() > date.today() + timedelta(days=365):
                raise ValueError('Closing date cannot be more than 1 year in the future')
        return v

class VacancyCreate(VacancyBase):
    pass

class VacancyUpdate(BaseModel):
    title: Optional[constr(min_length=3, max_length=255, strip_whitespace=True)] = None
    department: Optional[constr(min_length=2, max_length=255, strip_whitespace=True)] = None
    description: Optional[constr(max_length=5000, strip_whitespace=True)] = None
    requirements: Optional[constr(max_length=3000, strip_whitespace=True)] = None
    responsibilities: Optional[constr(max_length=3000, strip_whitespace=True)] = None
    nice_to_have_skills: Optional[constr(max_length=1000, strip_whitespace=True)] = None
    location: Optional[constr(max_length=255, strip_whitespace=True)] = None
    employment_type: Optional[Literal['full-time', 'part-time', 'contract', 'internship', 'temporary']] = None
    experience_required: Optional[constr(max_length=100, strip_whitespace=True)] = None
    salary_range: Optional[constr(max_length=100, strip_whitespace=True)] = None
    status: Optional[Literal['open', 'closed', 'on-hold', 'filled']] = None
    closing_date: Optional[datetime] = None
    posted_on_linkedin: Optional[bool] = None
    posted_on_naukri: Optional[bool] = None
    posted_on_indeed: Optional[bool] = None
    posted_on_other: Optional[bool] = None
    social_media_links: Optional[constr(max_length=1000)] = None

class VacancyOut(VacancyBase):
    vacancy_id: int = Field(..., gt=0)
    created_by: Optional[int] = Field(None, gt=0)
    created_at: datetime
    updated_at: Optional[datetime] = None
    posted_on_linkedin: bool
    posted_on_naukri: bool
    posted_on_indeed: bool
    posted_on_other: bool
    social_media_links: Optional[str] = None
    candidates_count: Optional[int] = Field(0, ge=0)

    model_config = {"from_attributes": True}

# Candidate Schemas
class CandidateBase(BaseModel):
    vacancy_id: int = Field(..., gt=0, description="Vacancy ID")
    name: constr(min_length=2, max_length=255, strip_whitespace=True) = Field(..., description="Candidate name")
    email: EmailStr = Field(..., description="Candidate email")
    phone: Optional[constr(min_length=10, max_length=20, strip_whitespace=True)] = Field(None, description="Phone number")
    cover_letter: Optional[constr(max_length=5000, strip_whitespace=True)] = Field(None, description="Cover letter")
    experience_years: Optional[int] = Field(None, ge=0, le=70, description="Years of experience (0-70)")
    current_company: Optional[constr(max_length=255, strip_whitespace=True)] = Field(None, description="Current company")
    current_position: Optional[constr(max_length=255, strip_whitespace=True)] = Field(None, description="Current position")
    expected_salary: Optional[constr(max_length=100, strip_whitespace=True)] = Field(None, description="Expected salary")
    notice_period: Optional[constr(max_length=100, strip_whitespace=True)] = Field(None, description="Notice period")
    source: Optional[Literal['linkedin', 'naukri', 'indeed', 'referral', 'website', 'other']] = Field(None, description="Application source")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate candidate name"""
        if not v or not v.strip():
            raise ValueError('Candidate name cannot be empty')
        if not re.match(r'^[a-zA-Z\s.]+$', v):
            raise ValueError('Name must contain only letters, spaces, and dots')
        return v.strip()

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number"""
        if v is not None:
            digits = re.sub(r'[^0-9]', '', v)
            if len(digits) < 10:
                raise ValueError('Phone number must have at least 10 digits')
            if len(digits) > 15:
                raise ValueError('Phone number cannot exceed 15 digits')
        return v

    @field_validator('experience_years')
    @classmethod
    def validate_experience(cls, v: Optional[int]) -> Optional[int]:
        """Validate experience years"""
        if v is not None:
            if v < 0:
                raise ValueError('Experience cannot be negative')
            if v > 70:
                raise ValueError('Experience years seems unreasonably high')
        return v

class CandidateCreate(CandidateBase):
    resume_url: Optional[str] = Field(None, description="Resume file URL")

class CandidateUpdate(BaseModel):
    name: Optional[constr(min_length=2, max_length=255, strip_whitespace=True)] = None
    email: Optional[EmailStr] = None
    phone: Optional[constr(min_length=10, max_length=20, strip_whitespace=True)] = None
    cover_letter: Optional[constr(max_length=5000, strip_whitespace=True)] = None
    experience_years: Optional[int] = Field(None, ge=0, le=70)
    current_company: Optional[constr(max_length=255, strip_whitespace=True)] = None
    current_position: Optional[constr(max_length=255, strip_whitespace=True)] = None
    expected_salary: Optional[constr(max_length=100, strip_whitespace=True)] = None
    notice_period: Optional[constr(max_length=100, strip_whitespace=True)] = None
    status: Optional[Literal['applied', 'screening', 'interview', 'offered', 'rejected', 'hired', 'withdrawn']] = None
    interview_date: Optional[datetime] = None
    interview_notes: Optional[constr(max_length=2000, strip_whitespace=True)] = None
    source: Optional[Literal['linkedin', 'naukri', 'indeed', 'referral', 'website', 'other']] = None

class CandidateOut(CandidateBase):
    candidate_id: int = Field(..., gt=0)
    resume_url: Optional[str] = None
    status: Literal['applied', 'screening', 'interview', 'offered', 'rejected', 'hired', 'withdrawn']
    interview_date: Optional[datetime] = None
    interview_notes: Optional[str] = None
    applied_at: datetime
    updated_at: Optional[datetime] = None
    vacancy_title: Optional[str] = None
    vacancy_department: Optional[str] = None

    model_config = {"from_attributes": True}

# Social Media Posting Schema
class SocialMediaPost(BaseModel):
    vacancy_id: int = Field(..., gt=0, description="Vacancy ID")
    platforms: List[Literal['linkedin', 'naukri', 'indeed', 'other']] = Field(..., min_length=1, description="Platforms to post on")
    links: Optional[dict] = Field(None, description="Platform-specific links")

    @field_validator('platforms')
    @classmethod
    def validate_platforms(cls, v: List[str]) -> List[str]:
        """Validate platforms list"""
        if not v:
            raise ValueError('At least one platform must be selected')
        # Remove duplicates
        return list(set(v))

