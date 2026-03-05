from pydantic import BaseModel, Field, field_validator, constr
from typing import Optional, List, Literal, Union
from datetime import datetime, date, timedelta
import json


class InterviewBase(BaseModel):
    """
    Base schema for *input* payloads (create/update).
    Enforces that start_time must be in the future.
    """

    candidate_id: int = Field(..., gt=0, description="Candidate ID")
    vacancy_id: int = Field(..., gt=0, description="Vacancy ID")
    start_time: datetime = Field(..., description="Interview start time in IST (Asia/Kolkata, UTC+05:30)")
    end_time: Optional[datetime] = Field(None, description="Interview end time in IST (optional)")
    mode: Optional[Literal['onsite', 'remote', 'phone']] = Field(None, description="Interview mode")
    location: Optional[constr(max_length=255, strip_whitespace=True)] = Field(None, description="Interview location (room/address/call link)")
    round_type: Optional[constr(max_length=100, strip_whitespace=True)] = Field(None, description="Interview round type (e.g., HR, Technical, Managerial)")
    panel_members: Optional[List[int]] = Field(None, description="List of user IDs of panel members")

    @field_validator('panel_members', mode='before')
    @classmethod
    def parse_panel_members(cls, v: Union[None, List[int], str]) -> Optional[List[int]]:
        """Parse panel_members from JSON string (DB storage) or list (API input)."""
        if v is None:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [parsed] if parsed is not None else None
            except json.JSONDecodeError:
                return None
        return None

    @field_validator('start_time')
    @classmethod
    def validate_start_time(cls, v: datetime) -> datetime:
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
            raise ValueError('Interview start time cannot be in the past')
        if (v_ist.date() - now_ist.date()).days > 365:
            raise ValueError('Interview start time cannot be more than 1 year in the future')
        
        return v_ist

    @field_validator('end_time')
    @classmethod
    def validate_end_time(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate end_time timezone conversion (start_time validation done in route)"""
        if v is None:
            return v
        
        try:
            from zoneinfo import ZoneInfo
            ist_tz = ZoneInfo("Asia/Kolkata")
            use_pytz = False
        except ImportError:
            try:
                import pytz
                ist_tz = pytz.timezone('Asia/Kolkata')
                use_pytz = True
            except ImportError:
                raise ValueError('Timezone support requires zoneinfo (Python 3.9+) or pytz library')
        
        # Convert to IST timezone-aware datetime
        if v.tzinfo is None:
            if use_pytz:
                v_ist = ist_tz.localize(v)
            else:
                v_ist = v.replace(tzinfo=ist_tz)
        else:
            v_ist = v.astimezone(ist_tz)
        
        return v_ist


class InterviewCreate(InterviewBase):
    pass


class InterviewBaseOut(BaseModel):
    """
    Base schema for *output* payloads (read-only).
    Does NOT enforce future-only start_time so that historical interviews can be returned.
    """

    candidate_id: int = Field(..., gt=0, description="Candidate ID")
    vacancy_id: int = Field(..., gt=0, description="Vacancy ID")
    start_time: datetime = Field(..., description="Interview start time in IST (Asia/Kolkata, UTC+05:30)")
    end_time: Optional[datetime] = Field(None, description="Interview end time in IST (optional)")
    mode: Optional[Literal['onsite', 'remote', 'phone']] = Field(None, description="Interview mode")
    location: Optional[constr(max_length=255, strip_whitespace=True)] = Field(None, description="Interview location (room/address/call link)")
    round_type: Optional[constr(max_length=100, strip_whitespace=True)] = Field(None, description="Interview round type (e.g., HR, Technical, Managerial)")
    panel_members: Optional[List[int]] = Field(None, description="List of user IDs of panel members")

    @field_validator('panel_members', mode='before')
    @classmethod
    def parse_panel_members(cls, v: Union[None, List[int], str]) -> Optional[List[int]]:
        """Parse panel_members from JSON string (DB storage) or list (API input)."""
        if v is None:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [parsed] if parsed is not None else None
            except json.JSONDecodeError:
                return None
        return None


class InterviewUpdate(BaseModel):
    start_time: Optional[datetime] = Field(None, description="Interview start time in IST")
    end_time: Optional[datetime] = Field(None, description="Interview end time in IST")
    mode: Optional[Literal['onsite', 'remote', 'phone']] = None
    location: Optional[constr(max_length=255, strip_whitespace=True)] = None
    round_type: Optional[constr(max_length=100, strip_whitespace=True)] = None
    status: Optional[Literal['scheduled', 'completed', 'cancelled', 'no_show', 'rescheduled']] = None
    # feedback_summary: Optional[constr(max_length=5000, strip_whitespace=True)] = None
    # rating: Optional[int] = Field(None, ge=1, le=5, description="Rating from 1 to 5")
    panel_members: Optional[List[int]] = None

    @field_validator('start_time')
    @classmethod
    def validate_start_time(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Convert datetime to IST timezone-aware and validate it's in the future"""
        if v is None:
            return v
        
        try:
            from zoneinfo import ZoneInfo
            ist_tz = ZoneInfo("Asia/Kolkata")
            use_pytz = False
        except ImportError:
            try:
                import pytz
                ist_tz = pytz.timezone('Asia/Kolkata')
                use_pytz = True
            except ImportError:
                raise ValueError('Timezone support requires zoneinfo (Python 3.9+) or pytz library')
        
        if v.tzinfo is None:
            if use_pytz:
                v_ist = ist_tz.localize(v)
            else:
                v_ist = v.replace(tzinfo=ist_tz)
        else:
            v_ist = v.astimezone(ist_tz)
        
        if use_pytz:
            now_ist = datetime.now(ist_tz)
        else:
            now_ist = datetime.now(ist_tz)
        
        if v_ist < now_ist:
            raise ValueError('Interview start time cannot be in the past')
        if (v_ist.date() - now_ist.date()).days > 365:
            raise ValueError('Interview start time cannot be more than 1 year in the future')
        
        return v_ist

    @field_validator('end_time')
    @classmethod
    def validate_end_time(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate end_time is in the future and after start_time if provided"""
        if v is None:
            return v
        
        try:
            from zoneinfo import ZoneInfo
            ist_tz = ZoneInfo("Asia/Kolkata")
            use_pytz = False
        except ImportError:
            try:
                import pytz
                ist_tz = pytz.timezone('Asia/Kolkata')
                use_pytz = True
            except ImportError:
                raise ValueError('Timezone support requires zoneinfo (Python 3.9+) or pytz library')
        
        if v.tzinfo is None:
            if use_pytz:
                v_ist = ist_tz.localize(v)
            else:
                v_ist = v.replace(tzinfo=ist_tz)
        else:
            v_ist = v.astimezone(ist_tz)
        
        return v_ist


class InterviewStatusOnlyUpdate(BaseModel):
    status: Literal['scheduled', 'completed', 'cancelled', 'no_show', 'rescheduled'] = Field(
        ..., description="New interview status"
    )


class InterviewOutBasic(InterviewBaseOut):
    """Interview response without feedback fields."""

    interview_id: int = Field(..., gt=0)
    status: Literal['scheduled', 'completed', 'cancelled', 'no_show', 'rescheduled']
    scheduled_by: Optional[int] = Field(None, gt=0)
    scheduled_at: datetime
    updated_at: Optional[datetime] = None

    # Denormalized fields for convenience
    candidate_name: Optional[str] = None
    vacancy_title: Optional[str] = None
    vacancy_department: Optional[str] = None

    model_config = {"from_attributes": True}


class InterviewOut(InterviewBaseOut):
    interview_id: int = Field(..., gt=0)
    status: Literal['scheduled', 'completed', 'cancelled', 'no_show', 'rescheduled']
    scheduled_by: Optional[int] = Field(None, gt=0)
    scheduled_at: datetime
    updated_at: Optional[datetime] = None
    
    # Denormalized fields for convenience
    candidate_name: Optional[str] = None
    vacancy_title: Optional[str] = None
    vacancy_department: Optional[str] = None
    
    model_config = {"from_attributes": True}
