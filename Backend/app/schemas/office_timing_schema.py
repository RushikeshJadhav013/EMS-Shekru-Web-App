from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator


class OfficeTimingBase(BaseModel):
    department: Optional[str] = Field(default=None, description="Department name or None for global setting")
    start_time: str = Field(..., description="Office start time in HH:MM format")
    end_time: str = Field(..., description="Office end time in HH:MM format")
    check_in_grace_minutes: int = Field(default=0, ge=0, le=180)
    check_out_grace_minutes: int = Field(default=0, ge=0, le=180)

    @validator("start_time", "end_time")
    def validate_time_format(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("Time must be in HH:MM format") from exc
        return value


class OfficeTimingCreate(OfficeTimingBase):
    pass


class OfficeTimingOut(OfficeTimingBase):
    id: int

    class Config:
        from_attributes = True
