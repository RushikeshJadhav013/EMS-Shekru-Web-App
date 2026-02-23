from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, Field, constr


class InterviewFeedbackBase(BaseModel):
    feedback_summary: constr(max_length=5000, strip_whitespace=True) = Field(
        ..., description="Detailed interview feedback"
    )
    rating: Optional[int] = Field(
        None, ge=1, le=5, description="Rating from 1 to 5"
    )
    strengths: Optional[constr(max_length=2000, strip_whitespace=True)] = Field(
        None, description="Candidate strengths"
    )
    weaknesses: Optional[constr(max_length=2000, strip_whitespace=True)] = Field(
        None, description="Areas of improvement"
    )
    recommendation: Optional[Literal["hire", "reject", "hold"]] = Field(
        None, description="Overall hiring recommendation"
    )


class InterviewFeedbackCreate(InterviewFeedbackBase):
    """Payload for creating new feedback for an interview."""


class InterviewFeedbackUpdate(BaseModel):
    feedback_summary: Optional[constr(max_length=5000, strip_whitespace=True)] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    strengths: Optional[constr(max_length=2000, strip_whitespace=True)] = None
    weaknesses: Optional[constr(max_length=2000, strip_whitespace=True)] = None
    recommendation: Optional[Literal["hire", "reject", "hold"]] = None


class InterviewFeedbackOut(InterviewFeedbackBase):
    id: int
    interview_id: int
    panel_member_id: int
    panel_member_name: Optional[str] = None
    panel_member_role: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

