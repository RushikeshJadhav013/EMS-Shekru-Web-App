from datetime import datetime
from pydantic import BaseModel


class BranchAdminAssignmentBase(BaseModel):
    admin_user_id: int


class BranchAdminAssignmentCreate(BranchAdminAssignmentBase):
    pass


class BranchAdminAssignmentOut(BaseModel):
    assignment_id: int
    admin_user_id: int
    branch_id: int
    is_active: bool
    created_at: datetime | None = None
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    class Config:
        from_attributes = True


class BranchAdminAssignmentStatusUpdate(BaseModel):
    is_active: bool

