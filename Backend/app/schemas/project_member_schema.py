from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field


class ProjectMemberAdd(BaseModel):
    user_id: int = Field(..., gt=0, description="User ID to add to project")
    role: Literal["pic", "manager", "member", "viewer"] = Field(
        "member", description="Role within the project"
    )


class ProjectMemberOut(BaseModel):
    id: int
    project_id: int
    user_id: int
    user_name: str
    user_role: str
    project_role: str
    is_active: bool
    added_at: datetime

    model_config = {"from_attributes": True}


class ProjectMembersBulkAdd(BaseModel):
    user_ids: list[int] = Field(..., min_length=1, description="List of user IDs to add to project")
    role: Literal["pic", "manager", "member", "viewer"] = Field(
        "member", description="Role within the project for all added users"
    )

