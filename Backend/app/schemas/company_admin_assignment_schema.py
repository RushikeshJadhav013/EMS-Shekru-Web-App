from datetime import datetime
from pydantic import BaseModel


class CompanyAdminAssignmentBase(BaseModel):
    admin_user_id: int


class CompanyAdminAssignmentCreate(CompanyAdminAssignmentBase):
    pass


class CompanyAdminAssignmentOut(BaseModel):
    assignment_id: int
    admin_user_id: int
    company_id: int
    is_active: bool
    created_at: datetime | None = None
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    class Config:
        from_attributes = True
