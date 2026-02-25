from datetime import date, datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, constr


class ProjectBase(BaseModel):
    name: constr(min_length=3, max_length=255, strip_whitespace=True) = Field(
        ..., description="Project name (3-255 characters)"
    )
    description: Optional[constr(max_length=5000, strip_whitespace=True)] = Field(
        None, description="Project description"
    )
    start_date: Optional[date] = Field(None, description="Planned start date")
    end_date: Optional[date] = Field(None, description="Planned end date")


class ProjectCreate(ProjectBase):
    """Payload for creating a project. PIC is always Admin/HR (current user)."""


class ProjectUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=255, strip_whitespace=True)] = None
    description: Optional[constr(max_length=5000, strip_whitespace=True)] = None
    status: Optional[Literal["planned", "in_progress", "completed", "archived"]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ProjectOut(ProjectBase):
    project_id: int = Field(..., gt=0)
    status: Literal["planned", "in_progress", "completed", "archived"]
    person_in_charge_id: Optional[int] = Field(None, gt=0)
    person_in_charge_name: Optional[str] = None
    created_by: Optional[int] = Field(None, gt=0)
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Denormalized counts
    member_count: Optional[int] = None
    task_count: Optional[int] = None

    model_config = {"from_attributes": True}

