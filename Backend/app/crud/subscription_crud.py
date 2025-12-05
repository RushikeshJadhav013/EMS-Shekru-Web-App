from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.db.models.subscription import SubscriptionPlan, AdminSubscription
from app.db.models.user import User
from app.schemas.subscription_schema import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    AdminSubscriptionCreate,
    AdminSubscriptionUpdate
)
from app.enums import RoleEnum
from datetime import datetime


# ==================== Subscription Plan CRUD ====================

def create_subscription_plan(
    db: Session,
    plan: SubscriptionPlanCreate,
    created_by: int = None
) -> SubscriptionPlan:
    """Create a new subscription plan"""
    db_plan = SubscriptionPlan(
        plan_name=plan.plan_name,
        description=plan.description,
        max_users=plan.max_users,
        price=plan.price,
        created_by=created_by
    )
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan


def get_subscription_plan(db: Session, plan_id: int) -> SubscriptionPlan:
    """Get a subscription plan by ID"""
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_id == plan_id).first()


def list_subscription_plans(
    db: Session,
    active_only: bool = False
) -> list[SubscriptionPlan]:
    """List all subscription plans"""
    query = db.query(SubscriptionPlan)
    if active_only:
        query = query.filter(SubscriptionPlan.is_active == True)
    return query.order_by(SubscriptionPlan.created_on.desc()).all()


def update_subscription_plan(
    db: Session,
    plan_id: int,
    plan_update: SubscriptionPlanUpdate,
    updated_by: int = None
) -> SubscriptionPlan:
    """Update a subscription plan"""
    plan = get_subscription_plan(db, plan_id)
    if not plan:
        return None
    
    update_data = plan_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)
    
    plan.updated_by = updated_by
    db.commit()
    db.refresh(plan)
    return plan


def delete_subscription_plan(db: Session, plan_id: int) -> SubscriptionPlan:
    """Delete a subscription plan (soft delete by setting is_active=False)"""
    plan = get_subscription_plan(db, plan_id)
    if not plan:
        return None
    
    # Check if any active subscriptions are using this plan
    active_subscriptions = db.query(AdminSubscription).filter(
        and_(
            AdminSubscription.plan_id == plan_id,
            AdminSubscription.is_active == True
        )
    ).count()
    
    if active_subscriptions > 0:
        # Soft delete instead of hard delete
        plan.is_active = False
        db.commit()
        db.refresh(plan)
    else:
        # Hard delete if no active subscriptions
        db.delete(plan)
        db.commit()
    
    return plan


# ==================== Admin Subscription CRUD ====================

def create_admin_subscription(
    db: Session,
    subscription: AdminSubscriptionCreate,
    created_by: int = None
) -> AdminSubscription:
    """Assign a subscription plan to an admin"""
    # Verify admin exists and is actually an admin
    admin = db.query(User).filter(
        and_(
            User.user_id == subscription.admin_id,
            User.role == RoleEnum.ADMIN
        )
    ).first()
    
    if not admin:
        raise ValueError("Admin not found or user is not an admin")
    
    # Check if admin already has a subscription
    existing = db.query(AdminSubscription).filter(
        AdminSubscription.admin_id == subscription.admin_id
    ).first()
    
    if existing:
        # Update existing subscription
        existing.plan_id = subscription.plan_id
        existing.start_date = datetime.now()
        existing.end_date = subscription.end_date
        existing.is_active = True
        existing.created_by = created_by
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new subscription
    db_subscription = AdminSubscription(
        admin_id=subscription.admin_id,
        plan_id=subscription.plan_id,
        end_date=subscription.end_date,
        created_by=created_by
    )
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription


def get_admin_subscription(
    db: Session,
    admin_id: int
) -> AdminSubscription:
    """Get subscription for a specific admin"""
    return (
        db.query(AdminSubscription)
        .filter(AdminSubscription.admin_id == admin_id)
        .first()
    )


def get_admin_subscription_by_id(
    db: Session,
    subscription_id: int
) -> AdminSubscription:
    """Get subscription by subscription ID"""
    return (
        db.query(AdminSubscription)
        .filter(AdminSubscription.subscription_id == subscription_id)
        .first()
    )


def list_admin_subscriptions(
    db: Session,
    active_only: bool = False
) -> list[AdminSubscription]:
    """List all admin subscriptions"""
    query = db.query(AdminSubscription)
    if active_only:
        query = query.filter(AdminSubscription.is_active == True)
    return query.order_by(AdminSubscription.created_on.desc()).all()


def update_admin_subscription(
    db: Session,
    subscription_id: int,
    subscription_update: AdminSubscriptionUpdate,
    updated_by: int = None
) -> AdminSubscription:
    """Update an admin subscription"""
    subscription = get_admin_subscription_by_id(db, subscription_id)
    if not subscription:
        return None
    
    update_data = subscription_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(subscription, key, value)
    
    subscription.updated_by = updated_by
    db.commit()
    db.refresh(subscription)
    return subscription


def delete_admin_subscription(
    db: Session,
    subscription_id: int
) -> AdminSubscription:
    """Delete an admin subscription"""
    subscription = get_admin_subscription_by_id(db, subscription_id)
    if not subscription:
        return None
    
    db.delete(subscription)
    db.commit()
    return subscription


# ==================== Helper Functions ====================

def get_admin_user_count(db: Session, admin_id: int) -> int:
    """Get the count of users created by a specific admin"""
    return (
        db.query(User)
        .filter(User.created_by == admin_id)
        .count()
    )


def check_admin_subscription_limit(
    db: Session,
    admin_id: int
) -> tuple[bool, int, int]:
    """
    Check if admin can create more users based on subscription limit.
    Returns: (can_create, current_count, max_allowed)
    """
    subscription = get_admin_subscription(db, admin_id)
    
    if not subscription or not subscription.is_active:
        return (False, 0, 0)
    
    # Check if subscription has expired
    if subscription.end_date and subscription.end_date < datetime.now():
        return (False, 0, 0)
    
    # Get the plan
    plan = subscription.plan
    if not plan or not plan.is_active:
        return (False, 0, 0)
    
    # Count users created by this admin
    current_count = get_admin_user_count(db, admin_id)
    max_allowed = plan.max_users
    
    can_create = current_count < max_allowed
    
    return (can_create, current_count, max_allowed)


def get_admin_subscription_info(
    db: Session,
    admin_id: int
) -> dict:
    """Get comprehensive subscription information for an admin"""
    subscription = get_admin_subscription(db, admin_id)
    
    if not subscription:
        return {
            "has_subscription": False,
            "current_count": 0,
            "max_allowed": 0,
            "can_create": False,
            "subscription": None
        }
    
    can_create, current_count, max_allowed = check_admin_subscription_limit(db, admin_id)
    
    return {
        "has_subscription": True,
        "current_count": current_count,
        "max_allowed": max_allowed,
        "can_create": can_create,
        "subscription": subscription,
        "plan": subscription.plan
    }

