from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.dependencies import get_current_super_admin
from app.db.models.super_admin import SuperAdmin
from app.db.models.subscription import SubscriptionPlan, AdminSubscription
from app.schemas.subscription_schema import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    SubscriptionPlanOut,
    AdminSubscriptionCreate,
    AdminSubscriptionUpdate,
    AdminSubscriptionOut,
    AdminSubscriptionWithPlan
)
from app.crud.subscription_crud import (
    create_subscription_plan,
    get_subscription_plan,
    list_subscription_plans,
    update_subscription_plan,
    delete_subscription_plan,
    create_admin_subscription,
    get_admin_subscription,
    get_admin_subscription_by_id,
    list_admin_subscriptions,
    update_admin_subscription,
    delete_admin_subscription,
    get_admin_subscription_info,
    check_admin_subscription_limit
)
from app.db.models.user import User
from app.enums import RoleEnum

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


# ==================== Subscription Plan Routes ====================

@router.post("/plans", response_model=SubscriptionPlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    plan: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Create a new subscription plan - Superadmin only"""
    # Check if plan name already exists
    existing = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.plan_name == plan.plan_name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A subscription plan with this name already exists"
        )
    
    return create_subscription_plan(db, plan, current_super_admin.super_admin_id)


@router.get("/plans", response_model=List[SubscriptionPlanOut])
def list_plans(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """List all subscription plans - Superadmin only"""
    return list_subscription_plans(db, active_only=active_only)


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanOut)
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Get a specific subscription plan - Superadmin only"""
    plan = get_subscription_plan(db, plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    return plan


@router.put("/plans/{plan_id}", response_model=SubscriptionPlanOut)
def update_plan(
    plan_id: int,
    plan_update: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Update a subscription plan - Superadmin only"""
    # Check if plan name is being updated and if it conflicts
    if plan_update.plan_name:
        existing = db.query(SubscriptionPlan).filter(
            and_(
                SubscriptionPlan.plan_name == plan_update.plan_name,
                SubscriptionPlan.plan_id != plan_id
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A subscription plan with this name already exists"
            )
    
    updated_plan = update_subscription_plan(
        db,
        plan_id,
        plan_update,
        current_super_admin.super_admin_id
    )
    
    if not updated_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    
    return updated_plan


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Delete a subscription plan - Superadmin only"""
    deleted_plan = delete_subscription_plan(db, plan_id)
    if not deleted_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    return None


# ==================== Admin Subscription Routes ====================

@router.post("/admin-subscriptions", response_model=AdminSubscriptionOut, status_code=status.HTTP_201_CREATED)
def assign_subscription(
    subscription: AdminSubscriptionCreate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Assign a subscription plan to an admin - Superadmin only"""
    # Verify admin exists
    admin = db.query(User).filter(
        and_(
            User.user_id == subscription.admin_id,
            User.role == RoleEnum.ADMIN
        )
    ).first()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found or user is not an admin"
        )
    
    # Verify plan exists
    plan = get_subscription_plan(db, subscription.plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    
    try:
        return create_admin_subscription(
            db,
            subscription,
            current_super_admin.super_admin_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/admin-subscriptions", response_model=List[AdminSubscriptionOut])
def list_admin_subscriptions_route(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """List all admin subscriptions - Superadmin only"""
    return list_admin_subscriptions(db, active_only=active_only)


@router.get("/admin-subscriptions/{subscription_id}", response_model=AdminSubscriptionOut)
def get_admin_subscription_route(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Get a specific admin subscription - Superadmin only"""
    subscription = get_admin_subscription_by_id(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin subscription not found"
        )
    return subscription


@router.get("/admin-subscriptions/admin/{admin_id}", response_model=AdminSubscriptionOut)
def get_admin_subscription_by_admin_route(
    admin_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Get subscription for a specific admin - Superadmin only"""
    subscription = get_admin_subscription(db, admin_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found for this admin"
        )
    return subscription


@router.put("/admin-subscriptions/{subscription_id}", response_model=AdminSubscriptionOut)
def update_admin_subscription_route(
    subscription_id: int,
    subscription_update: AdminSubscriptionUpdate,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Update an admin subscription - Superadmin only"""
    # Verify plan exists if plan_id is being updated
    if subscription_update.plan_id:
        plan = get_subscription_plan(db, subscription_update.plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription plan not found"
            )
    
    updated_subscription = update_admin_subscription(
        db,
        subscription_id,
        subscription_update,
        current_super_admin.super_admin_id
    )
    
    if not updated_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin subscription not found"
        )
    
    return updated_subscription


@router.delete("/admin-subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_subscription_route(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Delete an admin subscription - Superadmin only"""
    deleted_subscription = delete_admin_subscription(db, subscription_id)
    if not deleted_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin subscription not found"
        )
    return None


# ==================== Subscription Info Routes ====================

@router.get("/admin-subscriptions/admin/{admin_id}/info")
def get_admin_subscription_info_route(
    admin_id: int,
    db: Session = Depends(get_db),
    current_super_admin: SuperAdmin = Depends(get_current_super_admin)
):
    """Get comprehensive subscription information for an admin - Superadmin only"""
    # Verify admin exists
    admin = db.query(User).filter(
        and_(
            User.user_id == admin_id,
            User.role == RoleEnum.ADMIN
        )
    ).first()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    return get_admin_subscription_info(db, admin_id)

