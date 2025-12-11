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
from datetime import datetime, timedelta
from typing import Optional


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
    """
    List subscription plans.

    - active_only=True  -> only active plans
    - active_only=False -> only inactive plans (per current requirement)
    """
    query = db.query(SubscriptionPlan)
    query = query.filter(SubscriptionPlan.is_active == True) if active_only else query.filter(SubscriptionPlan.is_active == False)
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
        # Update existing subscription; new plan should start after the current term ends
        current_end = existing.end_date
        scheduled_start = current_end if current_end and current_end > datetime.now() else datetime.now()

        # Distinguish trial vs paid by duration (<=31 days treated as trial)
        existing_duration = (existing.end_date - existing.start_date) if (existing.end_date and existing.start_date) else None
        is_trial = bool(existing_duration and existing_duration.days <= 31)
        default_duration = timedelta(days=30) if is_trial else timedelta(days=365)

        existing.plan_id = subscription.plan_id
        existing.start_date = scheduled_start
        if subscription.end_date is not None:
            # Use provided end date but ensure it isn't before the scheduled start
            existing.end_date = max(subscription.end_date, scheduled_start)
        else:
            # Preserve the previous duration; fall back based on trial/paid heuristic
            preserved_duration = existing_duration or default_duration
            existing.end_date = scheduled_start + preserved_duration
        existing.is_active = True
        existing.created_by = created_by
        db.commit()
        db.refresh(existing)
        return existing
    
    # If no subscription exists, do NOT auto-assign a trial here.
    # A trial is assigned during admin creation; require explicit end_date when creating first subscription via this API.
    scheduled_start = datetime.now()
    if subscription.end_date is None:
        raise ValueError("No existing subscription found. Provide an explicit end_date for the new subscription (trials are assigned during admin creation).")

    db_subscription = AdminSubscription(
        admin_id=subscription.admin_id,
        plan_id=subscription.plan_id,
        start_date=scheduled_start,
        end_date=max(subscription.end_date, scheduled_start),
        is_active=True,
        created_by=created_by
    )
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription


def assign_trial_subscription_to_admin(
    db: Session,
    admin_id: int,
    created_by: Optional[int] = None
) -> Optional[AdminSubscription]:
    """
    Assign a 1-month trial subscription to the given admin.
    Picks the first active subscription plan (oldest created) for the trial.
    Returns None if no active plan exists.
    """
    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active == True)
        .order_by(SubscriptionPlan.created_on.asc())
        .first()
    )

    if not plan:
        return None

    trial_request = AdminSubscriptionCreate(admin_id=admin_id, plan_id=plan.plan_id)
    return create_admin_subscription(db, trial_request, created_by=created_by)


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

    # If admin accepts the subscription, set a 1-year tenure starting now
    if update_data.pop("accept_subscription", False):
        current_end = subscription.end_date
        scheduled_start = current_end if current_end and current_end > datetime.now() else datetime.now()
        subscription.start_date = scheduled_start
        subscription.end_date = scheduled_start + timedelta(days=365)
        subscription.is_active = True

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
    
    def _is_trial(sub: AdminSubscription) -> bool:
        """Heuristic: subscription created via trial helper (30-day window)."""
        if not sub or not sub.start_date or not sub.end_date:
            return False
        duration = sub.end_date - sub.start_date
        # Accept small drift (<= 31 days) as trial
        return duration.days <= 31

    if not subscription:
        return {
            "has_subscription": False,
            "current_count": 0,
            "max_allowed": 0,
            "can_create": False,
            "subscription": None,
            "is_trial": False,
            "trial_ends_on": None,
        }
    
    can_create, current_count, max_allowed = check_admin_subscription_limit(db, admin_id)
    
    return {
        "has_subscription": True,
        "current_count": current_count,
        "max_allowed": max_allowed,
        "can_create": can_create,
        "subscription": subscription,
        "plan": subscription.plan,
        "is_trial": _is_trial(subscription),
        "trial_ends_on": subscription.end_date,
    }

