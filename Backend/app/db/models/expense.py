
from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    String,
    ForeignKey,
    Numeric,
    Text,
    Date,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Expense(Base):
    __tablename__ = "expenses"

    expense_id = Column(Integer, primary_key=True, index=True)

    company_id = Column(
        Integer,
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Expense details
    category = Column(String(100), nullable=False)
    sub_category = Column(String(100), nullable=False)
    expense_date = Column(DateTime, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(Text, nullable=True)

    # Vendor and invoice details
    vendor_id = Column(
        Integer,
        ForeignKey("vendors.vendor_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invoice_number = Column(String(100), nullable=True)
    invoice_date = Column(Date, nullable=True)
    gst_number = Column(String(30), nullable=True)
    gst_amount = Column(Numeric(10, 2), nullable=True)

    # Organization and project details
    cost_center = Column(String(100), nullable=True)
    project_name = Column(String(150), nullable=True)
    client_name = Column(String(150), nullable=True)

    # Approval workflow
    status = Column(
        String(50),
        nullable=False,
        default="Pending",
        index=True,
    )
    approved_amount = Column(Numeric(10, 2), nullable=True)
    approved_by = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Payment details
    payment_mode = Column(String(50), nullable=True)
    payment_date = Column(Date, nullable=True)
    transaction_reference = Column(String(150), nullable=True)
    payment_status = Column(
        String(50),
        nullable=False,
        default="Unpaid",
    )
    paid_by = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    closed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", foreign_keys=[user_id])
    vendor = relationship("Vendor")
    approver = relationship("User", foreign_keys=[approved_by])
    payer = relationship("User", foreign_keys=[paid_by])

    documents = relationship(
        "ExpenseDocument",
        cascade="all, delete-orphan",
    )
