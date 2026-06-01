from sqlalchemy import Column, Integer, DateTime, func, Boolean, ForeignKey
from app.db.database import Base


class LeaveAllocationConfig(Base):
    """
    Per-company leave allocation configuration set by admin.
    Defines how annual leave is distributed across leave types.
    """
    __tablename__ = "leave_allocation_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Total annual leave allocation
    total_annual_leave = Column(Integer, nullable=False, default=15)

    # Distribution of annual leave across types
    sick_leave_allocation = Column(Integer, nullable=False, default=10)
    casual_leave_allocation = Column(Integer, nullable=False, default=5)
    other_leave_allocation = Column(Integer, nullable=False, default=0)

    # Metadata
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by = Column(Integer, nullable=True)  # User ID of admin who updated

    def __repr__(self):
        return (
            f"<LeaveAllocationConfig(company_id={self.company_id}, "
            f"total={self.total_annual_leave}, sick={self.sick_leave_allocation}, "
            f"casual={self.casual_leave_allocation}, other={self.other_leave_allocation})>"
        )
