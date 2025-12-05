from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from decimal import Decimal


class SubscriptionPlanBase(BaseModel):
    plan_name: str
    description: Optional[str] = None
    max_users: int
    price: Decimal
    
    @validator("max_users")
    def validate_max_users(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Maximum users must be greater than 0")
        return v
    
    @validator("price")
    def validate_price(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Price cannot be negative")
        return v


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass


class SubscriptionPlanUpdate(BaseModel):
    plan_name: Optional[str] = None
    description: Optional[str] = None
    max_users: Optional[int] = None
    price: Optional[Decimal] = None
    is_active: Optional[bool] = None
    
    @validator("max_users")
    def validate_max_users(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Maximum users must be greater than 0")
        return v
    
    @validator("price")
    def validate_price(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Price cannot be negative")
        return v


class SubscriptionPlanOut(SubscriptionPlanBase):
    plan_id: int
    is_active: bool
    created_on: datetime
    updated_on: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


class AdminSubscriptionBase(BaseModel):
    admin_id: int
    plan_id: int
    end_date: Optional[datetime] = None


class AdminSubscriptionCreate(AdminSubscriptionBase):
    pass


class AdminSubscriptionUpdate(BaseModel):
    plan_id: Optional[int] = None
    is_active: Optional[bool] = None
    end_date: Optional[datetime] = None


class AdminSubscriptionOut(BaseModel):
    subscription_id: int
    admin_id: int
    plan_id: int
    is_active: bool
    start_date: datetime
    end_date: Optional[datetime] = None
    created_on: datetime
    updated_on: Optional[datetime] = None
    plan: Optional[SubscriptionPlanOut] = None
    
    model_config = {"from_attributes": True}


class AdminSubscriptionWithPlan(AdminSubscriptionOut):
    """Admin subscription with full plan details"""
    plan: SubscriptionPlanOut

