"""
Work From Home (WFH) Request Model
Stores WFH requests submitted by employees for Manager/HR approval.
"""
from sqlalchemy import Column, Integer, DateTime, String, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.utils.timezone import now_ist
from enum import Enum


class WFHStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class WFHType(str, Enum):
    FULL_DAY = "Full Day"
    HALF_DAY = "Half Day"


class WFHRequest(Base):
    __tablename__ = "wfh_requests"

    wfh_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    
    # Request details
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    wfh_type = Column(String(50), default=WFHType.FULL_DAY.value)  # Full Day or Half Day
    reason = Column(Text, nullable=False)
    
    # Status tracking
    status = Column(String(50), default=WFHStatus.PENDING.value)
    
    # Approval details
    approved_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=now_ist, nullable=False)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="wfh_requests")
    approver = relationship("User", foreign_keys=[approved_by])

