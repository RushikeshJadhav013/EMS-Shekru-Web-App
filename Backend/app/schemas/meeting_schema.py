from datetime import datetime
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field


class MeetingBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    meeting_url: AnyHttpUrl


class MeetingCreate(MeetingBase):
    participant_ids: List[int] = Field(default_factory=list)


class MeetingUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    meeting_url: Optional[AnyHttpUrl] = None
    participant_ids: Optional[List[int]] = None


class MeetingParticipantsAdd(BaseModel):
    user_ids: List[int]


class MeetingParticipantOut(BaseModel):
    id: int
    user_id: int
    user_name: str

    model_config = {"from_attributes": True}


class MeetingOut(MeetingBase):
    id: int
    created_by_id: int
    created_by_name: Optional[str] = None
    created_at: datetime
    participants: List[MeetingParticipantOut] = []

    model_config = {"from_attributes": True}

