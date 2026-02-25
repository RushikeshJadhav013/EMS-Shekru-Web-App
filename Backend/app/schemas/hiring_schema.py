from pydantic import BaseModel, EmailStr, Field, field_validator, constr
from typing import Optional, List, Literal
from datetime import datetime, date, timedelta, timezone
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

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: EmailStr) -> EmailStr:
        """Normalize email to lowercase for consistent uniqueness checks."""
        return v.lower()

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number: exactly 10 digits, starting with 6/7/8/9."""
        if v is None:
            return v

        # Keep only digits for validation and storage
        digits = re.sub(r'[^0-9]', '', v)

        if len(digits) != 10:
            raise ValueError('Phone number must have exactly 10 digits')

        if not re.match(r'^[6-9]', digits):
            raise ValueError('Phone number must start with 6, 7, 8, or 9')

        # Store normalized 10-digit phone
        return digits

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
    source: Optional[Literal['linkedin', 'naukri', 'indeed', 'referral', 'website', 'other']] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number on update: exactly 10 digits, starting with 6/7/8/9."""
        if v is None:
            return v

        digits = re.sub(r'[^0-9]', '', v)

        if len(digits) != 10:
            raise ValueError('Phone number must have exactly 10 digits')

        if not re.match(r'^[6-9]', digits):
            raise ValueError('Phone number must start with 6, 7, 8, or 9')

        return digits

class CandidateOutNoInterview(CandidateBase):
    candidate_id: int = Field(..., gt=0)
    resume_url: Optional[str] = None
    status: Literal['applied', 'screening', 'interview', 'offered', 'rejected', 'hired', 'withdrawn']
    applied_at: datetime
    updated_at: Optional[datetime] = None
    vacancy_title: Optional[str] = None
    vacancy_department: Optional[str] = None

    model_config = {"from_attributes": True}


class CandidateOut(CandidateOutNoInterview):
    """Extended candidate response that includes interview_date when needed (e.g., shortlist APIs)."""
    interview_date: Optional[datetime] = None  # Denormalized: next upcoming interview date from interviews table

class CandidateShortlist(BaseModel):
    interview_date: datetime = Field(..., description="Scheduled interview date and time in IST (Asia/Kolkata, UTC+05:30). Accepts timezone-aware (converted to IST) or naive datetime (assumed IST)")
    interview_notes: Optional[constr(max_length=2000, strip_whitespace=True)] = Field(None, description="Optional notes about the interview")

    @field_validator('interview_date')
    @classmethod
    def validate_interview_date(cls, v: datetime) -> datetime:
        """Convert datetime to IST timezone-aware and validate it's in the future"""
        try:
            from zoneinfo import ZoneInfo
            ist_tz = ZoneInfo("Asia/Kolkata")
            use_pytz = False
        except ImportError:
            # Fallback for Python < 3.9
            try:
                import pytz
                ist_tz = pytz.timezone('Asia/Kolkata')
                use_pytz = True
            except ImportError:
                raise ValueError('Timezone support requires zoneinfo (Python 3.9+) or pytz library')
        
        # Convert to IST timezone-aware datetime
        if v.tzinfo is None:
            # Naive datetime: assume it's already in IST
            if use_pytz:
                v_ist = ist_tz.localize(v)
            else:
                v_ist = v.replace(tzinfo=ist_tz)
        else:
            # Timezone-aware: convert to IST
            v_ist = v.astimezone(ist_tz)
        
        # Get current time in IST for comparison
        if use_pytz:
            now_ist = datetime.now(ist_tz)
        else:
            now_ist = datetime.now(ist_tz)
        
        if v_ist < now_ist:
            raise ValueError('Interview date cannot be in the past')
        if (v_ist.date() - now_ist.date()).days > 365:
            raise ValueError('Interview date cannot be more than 1 year in the future')
        
        return v_ist

class CandidateStatusUpdate(BaseModel):
    status: Literal['applied', 'screening', 'interview', 'offered', 'rejected', 'hired', 'withdrawn'] = Field(..., description="New status for the candidate")
    interview_date: Optional[datetime] = Field(None, description="Optional: Create a new interview when setting status to 'interview' (in IST)")
    interview_notes: Optional[constr(max_length=2000, strip_whitespace=True)] = Field(None, description="Optional: Notes for the interview (if creating new interview)")

    @field_validator('interview_date')
    @classmethod
    def validate_interview_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Convert datetime to IST timezone-aware and validate it's in the future"""
        if v is None:
            return v
        
        try:
            from zoneinfo import ZoneInfo
            ist_tz = ZoneInfo("Asia/Kolkata")
            use_pytz = False
        except ImportError:
            # Fallback for Python < 3.9
            try:
                import pytz
                ist_tz = pytz.timezone('Asia/Kolkata')
                use_pytz = True
            except ImportError:
                raise ValueError('Timezone support requires zoneinfo (Python 3.9+) or pytz library')
        
        # Convert to IST timezone-aware datetime
        if v.tzinfo is None:
            # Naive datetime: assume it's already in IST
            if use_pytz:
                v_ist = ist_tz.localize(v)
            else:
                v_ist = v.replace(tzinfo=ist_tz)
        else:
            # Timezone-aware: convert to IST
            v_ist = v.astimezone(ist_tz)
        
        # Get current time in IST for comparison
        if use_pytz:
            now_ist = datetime.now(ist_tz)
        else:
            now_ist = datetime.now(ist_tz)
        
        if v_ist < now_ist:
            raise ValueError('Interview date cannot be in the past')
        if (v_ist.date() - now_ist.date()).days > 365:
            raise ValueError('Interview date cannot be more than 1 year in the future')
        
        return v_ist

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status value"""
        valid_statuses = ['applied', 'screening', 'interview', 'offered', 'rejected', 'hired', 'withdrawn']
        if v not in valid_statuses:
            raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v

# Social Media Posting Schema
class SocialMediaPost(BaseModel):
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

