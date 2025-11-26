from pydantic import BaseModel, EmailStr

class SuperAdminBase(BaseModel):
    name: str
    email: EmailStr
    contact_no: str

class SuperAdminCreate(SuperAdminBase):
    pass

class SuperAdminUpdate(SuperAdminBase):
    name: str | None = None
    email: EmailStr | None = None
    contact_no: str | None = None
