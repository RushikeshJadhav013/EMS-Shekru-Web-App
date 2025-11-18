from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DepartmentBase(BaseModel):
    name: str
    code: str
    manager_id: Optional[int] = None
    description: Optional[str] = None
    status: str = "active"
    employee_count: Optional[int] = None
    budget: Optional[float] = None
    location: Optional[str] = None


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    manager_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None
    employee_count: Optional[int] = None
    budget: Optional[float] = None
    location: Optional[str] = None


class DepartmentOut(DepartmentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


