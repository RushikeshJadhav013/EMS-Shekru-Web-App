from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, func, UniqueConstraint

from app.db.database import Base


class CompanyAdminAssignment(Base):
    """
    Maps admin users directly to a company (no branch required).
    Use together with branch_admin_assignments for branch-scoped admins.
    """

    __tablename__ = "company_admin_assignments"
    __table_args__ = (
        UniqueConstraint("admin_user_id", "company_id", name="uq_company_admin_user"),
    )

    assignment_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    admin_user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        Integer,
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(
        Integer,
        ForeignKey("super_admins.super_admin_id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by = Column(
        Integer,
        ForeignKey("super_admins.super_admin_id", ondelete="SET NULL"),
        nullable=True,
    )
