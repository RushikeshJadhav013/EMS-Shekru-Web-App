from datetime import datetime
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator


class MeetingBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Meeting title")
    description: Optional[str] = Field(None, max_length=2000, description="Meeting description")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    meeting_url: AnyHttpUrl

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Meeting title cannot be empty or whitespace only.")
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Meeting description cannot be empty or whitespace only.")
            return v.strip()
        return v


class MeetingCreate(MeetingBase):
    title: str = Field(..., min_length=1, max_length=255, description="Meeting title")
    description: str = Field(..., min_length=1, max_length=2000, description="Meeting description")
    participant_ids: List[int] = Field(..., min_length=1, description="List of participant user IDs (at least 1 required)")

    @field_validator("title")
    @classmethod
    def validate_title_create(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Meeting title cannot be empty or whitespace only.")
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description_create(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Meeting description cannot be empty or whitespace only.")
        return v.strip()

    @field_validator("participant_ids")
    @classmethod
    def validate_participant_ids(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("At least one participant must be selected for the meeting.")
        valid_ids = [uid for uid in v if uid is not None and uid > 0]
        if not valid_ids:
            raise ValueError("At least one valid participant ID (greater than 0) must be provided.")
        return valid_ids


class ProjectMeetingCreate(MeetingBase):
    title: str = Field(..., min_length=1, max_length=255, description="Meeting title")
    description: str = Field(..., min_length=1, max_length=2000, description="Meeting description")
    participant_ids: Optional[List[int]] = Field(
        default_factory=list,
        description="Optional list of project member user IDs. If empty or omitted, all active project members are included.",
    )

    @field_validator("title")
    @classmethod
    def validate_title_project(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Meeting title cannot be empty or whitespace only.")
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description_project(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Meeting description cannot be empty or whitespace only.")
        return v.strip()

    @field_validator("participant_ids")
    @classmethod
    def validate_participant_ids_project(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v:
            valid_ids = [uid for uid in v if uid is not None and uid > 0]
            if not valid_ids:
                raise ValueError("If participants are provided, at least one valid participant ID must be included.")
            return valid_ids
        return v


class MeetingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    meeting_url: Optional[AnyHttpUrl] = None
    participant_ids: Optional[List[int]] = None

    @field_validator("title")
    @classmethod
    def validate_title_update(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Meeting title cannot be empty or whitespace only.")
            return v.strip()
        return v

    @field_validator("description")
    @classmethod
    def validate_description_update(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Meeting description cannot be empty or whitespace only.")
            return v.strip()
        return v

    @field_validator("participant_ids")
    @classmethod
    def validate_participant_ids_update(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None:
            if not v:
                raise ValueError("At least one participant must be provided when updating participants.")
            valid_ids = [uid for uid in v if uid is not None and uid > 0]
            if not valid_ids:
                raise ValueError("At least one valid participant ID (greater than 0) must be provided.")
            return valid_ids
        return v


class MeetingParticipantsAdd(BaseModel):
    user_ids: List[int] = Field(..., min_length=1, description="List of user IDs to add")

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("At least one user ID must be provided.")
        valid_ids = [uid for uid in v if uid is not None and uid > 0]
        if not valid_ids:
            raise ValueError("At least one valid user ID (greater than 0) must be provided.")
        return valid_ids


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
    description: Optional[str] = None
    participants: List[MeetingParticipantOut] = []

    model_config = {"from_attributes": True}


class MeetingNotificationOut(BaseModel):
    notification_id: int = Field(..., gt=0, description="Notification ID")
    user_id: int = Field(..., gt=0, description="User ID")
    meeting_id: Optional[int] = Field(None, gt=0, description="Meeting ID (nullable for deletions)")
    notification_type: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=1000)
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}

