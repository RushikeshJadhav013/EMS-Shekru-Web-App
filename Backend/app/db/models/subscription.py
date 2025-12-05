from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric, func
from sqlalchemy.orm import relationship
from app.db.database import Base


class SubscriptionPlan(Base):
    """Subscription plans created by superadmin"""
    __tablename__ = "subscription_plans"

    plan_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    plan_name = Column(String(255), nullable=False, unique=True)
    description = Column(String(500), nullable=True)
    
    # Plan limits
    max_users = Column(Integer, nullable=False)  # Maximum number of users allowed
    
    # Pricing (in rupees)
    price = Column(Numeric(10, 2), nullable=False)  # Price in INR
    
    # Plan status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit fields
    created_on = Column(DateTime(timezone=True), server_default=func.now())
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(
        Integer,
        ForeignKey("super_admins.super_admin_id", ondelete="SET NULL"),
        nullable=True
    )
    updated_by = Column(
        Integer,
        ForeignKey("super_admins.super_admin_id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Relationships
    admin_subscriptions = relationship("AdminSubscription", back_populates="plan", cascade="all, delete-orphan")


class AdminSubscription(Base):
    """Tracks which admin has which subscription plan"""
    __tablename__ = "admin_subscriptions"

    subscription_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    admin_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True  # One subscription per admin
    )
    plan_id = Column(
        Integer,
        ForeignKey("subscription_plans.plan_id", ondelete="RESTRICT"),
        nullable=False
    )
    
    # Subscription status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Subscription dates
    start_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)  # Null means no expiry
    
    # Audit fields
    created_on = Column(DateTime(timezone=True), server_default=func.now())
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(
        Integer,
        ForeignKey("super_admins.super_admin_id", ondelete="SET NULL"),
        nullable=True
    )
    updated_by = Column(
        Integer,
        ForeignKey("super_admins.super_admin_id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Relationships
    admin = relationship("User", foreign_keys=[admin_id])
    plan = relationship("SubscriptionPlan", back_populates="admin_subscriptions")

