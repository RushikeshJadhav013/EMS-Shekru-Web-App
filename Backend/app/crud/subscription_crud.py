from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.db.models.subscription import (
    SubscriptionPlan,
    AdminSubscription,
    CompanySubscription,
    BranchSubscription,
)
from app.db.models.user import User
from app.db.models.company import Company
from app.db.models.company_branch import CompanyBranch
from app.schemas.subscription_schema import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    AdminSubscriptionCreate,
    AdminSubscriptionUpdate,
    CompanySubscriptionCreate,
    CompanySubscriptionUpdate,
    BranchSubscriptionCreate,
    BranchSubscriptionUpdate,
)
from app.enums import RoleEnum
from datetime import datetime, timedelta
from typing import Optional
import calendar


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
        duration_months=plan.duration_months,
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
    active_only: Optional[bool] = None
) -> list[SubscriptionPlan]:
    """
    List subscription plans.

    - active_only=True  -> only active plans
    - active_only=False -> only inactive plans
    - active_only=None  -> all plans (default)
    """
    query = db.query(SubscriptionPlan)
    if active_only is True:
        query = query.filter(SubscriptionPlan.is_active == True)  # noqa: E712
    elif active_only is False:
        query = query.filter(SubscriptionPlan.is_active == False)  # noqa: E712
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
    active_admin = db.query(AdminSubscription).filter(
        and_(AdminSubscription.plan_id == plan_id, AdminSubscription.is_active == True)  # noqa: E712
    ).count()
    active_company = db.query(CompanySubscription).filter(
        and_(CompanySubscription.plan_id == plan_id, CompanySubscription.is_active == True)  # noqa: E712
    ).count()
    active_branch = db.query(BranchSubscription).filter(
        and_(BranchSubscription.plan_id == plan_id, BranchSubscription.is_active == True)  # noqa: E712
    ).count()
    active_subscriptions = active_admin + active_company + active_branch
    
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

        existing_duration = (
            (existing.end_date - existing.start_date)
            if (existing.end_date and existing.start_date)
            else None
        )
        default_duration = timedelta(days=365)

        existing.plan_id = subscription.plan_id
        existing.start_date = scheduled_start
        if subscription.end_date is not None:
            # Use provided end date but ensure it isn't before the scheduled start
            existing.end_date = max(subscription.end_date, scheduled_start)
        else:
            # Preserve the previous duration; fall back to 1 year
            preserved_duration = existing_duration or default_duration
            existing.end_date = scheduled_start + preserved_duration
        existing.is_active = True
        existing.created_by = created_by
        db.commit()
        db.refresh(existing)
        return existing
    
    # If no subscription exists, do NOT auto-assign any free trial.
    # Require explicit end_date (or set end_date to NULL via DB if you intend "no expiry").
    scheduled_start = datetime.now()
    if subscription.end_date is None:
        raise ValueError("No existing subscription found. Provide an explicit end_date for the new subscription.")

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
    """
    Get the count of users for an admin.
    Note: User model has no created_by column, so fall back to total users.
    """
    return db.query(User).count()


def check_admin_subscription_limit(
    db: Session,
    admin_id: int
) -> tuple[bool, int, int]:
    """
    Check if admin can create more users based on subscription limit.
    Returns: (can_create, current_count, max_allowed)
    If no active subscription exists, allows unlimited user creation.
    """
    subscription = get_admin_subscription(db, admin_id)
    
    # If no subscription or inactive, allow unlimited user creation
    if not subscription or not subscription.is_active:
        current_count = get_admin_user_count(db, admin_id)
        return (True, current_count, float('inf'))
    
    # Check if subscription has expired
    if subscription.end_date and subscription.end_date < datetime.now():
        current_count = get_admin_user_count(db, admin_id)
        return (True, current_count, float('inf'))
    
    # Get the plan
    plan = subscription.plan
    if not plan or not plan.is_active:
        current_count = get_admin_user_count(db, admin_id)
        return (True, current_count, float('inf'))
    
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

    # Use check_admin_subscription_limit to get accurate limits (handles no subscription case)
    can_create, current_count, max_allowed = check_admin_subscription_limit(db, admin_id)
    
    if not subscription:
        return {
            "has_subscription": False,
            "current_count": current_count,
            "max_allowed": max_allowed if max_allowed != float('inf') else None,  # Show None for unlimited
            "can_create": can_create,
            "subscription": None,
            "is_trial": False,
            "trial_ends_on": None,
        }
    
    return {
        "has_subscription": True,
        "current_count": current_count,
        "max_allowed": max_allowed,
        "can_create": can_create,
        "subscription": subscription,
        "plan": subscription.plan,
        # No free trial concept: keep fields for backwards compatibility but always false.
        "is_trial": False,
        "trial_ends_on": None,
    }


# ==================== Company/Branch Subscription CRUD ====================

def _add_months(dt: datetime, months: int) -> datetime:
    """Add calendar months to a datetime (keeps time, clamps day)."""
    if months <= 0:
        return dt
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def assign_company_subscription(
    db: Session,
    subscription: CompanySubscriptionCreate,
    created_by: int | None = None,
) -> CompanySubscription:
    """Assign (or replace) a subscription plan for a company."""
    company = db.query(Company).filter(Company.company_id == subscription.company_id).first()
    if not company:
        raise ValueError("Company not found")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_id == subscription.plan_id).first()
    if not plan or not plan.is_active:
        raise ValueError("Subscription plan not found or inactive")

    existing = db.query(CompanySubscription).filter(CompanySubscription.company_id == subscription.company_id).first()
    start = datetime.now()
    end = _add_months(start, int(plan.duration_months))

    if existing:
        existing.plan_id = subscription.plan_id
        existing.start_date = start
        existing.end_date = end
        existing.is_active = True
        existing.updated_by = created_by
        db.commit()
        db.refresh(existing)
        return existing

    db_sub = CompanySubscription(
        company_id=subscription.company_id,
        plan_id=subscription.plan_id,
        start_date=start,
        end_date=end,
        is_active=True,
        created_by=created_by,
    )
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return db_sub


def assign_branch_subscription(
    db: Session,
    subscription: BranchSubscriptionCreate,
    created_by: int | None = None,
) -> BranchSubscription:
    """Assign (or replace) a subscription plan for a branch."""
    branch = db.query(CompanyBranch).filter(CompanyBranch.branch_id == subscription.branch_id).first()
    if not branch or getattr(branch, "is_deleted", False):
        raise ValueError("Branch not found")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_id == subscription.plan_id).first()
    if not plan or not plan.is_active:
        raise ValueError("Subscription plan not found or inactive")

    existing = db.query(BranchSubscription).filter(BranchSubscription.branch_id == subscription.branch_id).first()
    start = datetime.now()
    end = _add_months(start, int(plan.duration_months))

    if existing:
        existing.plan_id = subscription.plan_id
        existing.start_date = start
        existing.end_date = end
        existing.is_active = True
        existing.updated_by = created_by
        db.commit()
        db.refresh(existing)
        return existing

    db_sub = BranchSubscription(
        branch_id=subscription.branch_id,
        plan_id=subscription.plan_id,
        start_date=start,
        end_date=end,
        is_active=True,
        created_by=created_by,
    )
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return db_sub


def get_company_subscription(db: Session, company_id: int) -> Optional[CompanySubscription]:
    return db.query(CompanySubscription).filter(CompanySubscription.company_id == company_id).first()


def get_branch_subscription(db: Session, branch_id: int) -> Optional[BranchSubscription]:
    return db.query(BranchSubscription).filter(BranchSubscription.branch_id == branch_id).first()


def update_company_subscription(
    db: Session,
    subscription_id: int,
    update: CompanySubscriptionUpdate,
    updated_by: int | None = None,
) -> Optional[CompanySubscription]:
    sub = db.query(CompanySubscription).filter(CompanySubscription.subscription_id == subscription_id).first()
    if not sub:
        return None
    data = update.model_dump(exclude_unset=True)
    if "plan_id" in data and data["plan_id"] is not None:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_id == data["plan_id"]).first()
        if not plan or not plan.is_active:
            raise ValueError("Subscription plan not found or inactive")
        # Reset term on plan change
        start = datetime.now()
        sub.plan_id = data["plan_id"]
        sub.start_date = start
        sub.end_date = _add_months(start, int(plan.duration_months))
        data.pop("plan_id", None)
    for k, v in data.items():
        setattr(sub, k, v)
    sub.updated_by = updated_by
    db.commit()
    db.refresh(sub)
    return sub


def update_branch_subscription(
    db: Session,
    subscription_id: int,
    update: BranchSubscriptionUpdate,
    updated_by: int | None = None,
) -> Optional[BranchSubscription]:
    sub = db.query(BranchSubscription).filter(BranchSubscription.subscription_id == subscription_id).first()
    if not sub:
        return None
    data = update.model_dump(exclude_unset=True)
    if "plan_id" in data and data["plan_id"] is not None:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_id == data["plan_id"]).first()
        if not plan or not plan.is_active:
            raise ValueError("Subscription plan not found or inactive")
        start = datetime.now()
        sub.plan_id = data["plan_id"]
        sub.start_date = start
        sub.end_date = _add_months(start, int(plan.duration_months))
        data.pop("plan_id", None)
    for k, v in data.items():
        setattr(sub, k, v)
    sub.updated_by = updated_by
    db.commit()
    db.refresh(sub)
    return sub


def check_company_branch_subscription_limit(
    db: Session,
    company_id: int,
    branch_id: Optional[int] = None,
) -> tuple[bool, int, int]:
    """
    Check if a scoped tenant can create more users based on subscription.
    Rule: if branch_id has active, non-expired subscription -> use it, else use company subscription.
    If no subscription found -> unlimited (current behavior).
    """
    now = datetime.now()

    # Count current users in scope
    if branch_id is not None:
        current_count = db.query(User).filter(User.company_id == company_id, User.branch_id == branch_id).count()
    else:
        current_count = db.query(User).filter(User.company_id == company_id).count()

    def _active_and_valid(end_date: Optional[datetime], is_active: bool) -> bool:
        if not is_active:
            return False
        if end_date is None:
            return True
        return end_date >= now

    # Prefer branch subscription when branch scope is present
    if branch_id is not None:
        bsub = get_branch_subscription(db, branch_id)
        if bsub and _active_and_valid(bsub.end_date, bsub.is_active) and bsub.plan and bsub.plan.is_active:
            max_allowed = int(bsub.plan.max_users)
            return (current_count < max_allowed, current_count, max_allowed)

    csub = get_company_subscription(db, company_id)
    if csub and _active_and_valid(csub.end_date, csub.is_active) and csub.plan and csub.plan.is_active:
        max_allowed = int(csub.plan.max_users)
        return (current_count < max_allowed, current_count, max_allowed)

    # No subscription -> unlimited
    return (True, current_count, float("inf"))

