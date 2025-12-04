from datetime import datetime
from pydantic import BaseModel, EmailStr

class SuperAdminBase(BaseModel):
    name: str
    email: EmailStr
    contact_no: str
    gender: str | None = None

class SuperAdminCreate(SuperAdminBase):
    pass

class SuperAdminUpdate(SuperAdminBase):
    name: str | None = None
    email: EmailStr | None = None
    contact_no: str | None = None
    gender: str | None = None


class SuperAdminOut(SuperAdminBase):
    super_admin_id: int
    is_active: bool
    created_on: datetime | None = None
    updated_on: datetime | None = None
    created_by: int | None = None
    updated_by: int | None = None

    class Config:
        from_attributes = True
