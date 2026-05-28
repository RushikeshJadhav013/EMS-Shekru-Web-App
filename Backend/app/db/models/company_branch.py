from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    func,
    UniqueConstraint,
)
from app.db.database import Base


class CompanyBranch(Base):
    __tablename__ = "company_branches"
    __table_args__ = (
        UniqueConstraint("company_id", "branch_name", name="uq_company_branch_name"),
        # Global uniqueness: same contact number cannot exist in multiple companies/branches.
        UniqueConstraint("contact_number", name="uq_company_branch_contact_global"),
        # Global uniqueness: branch email cannot repeat across branches.
        UniqueConstraint("branch_email", name="uq_company_branch_email_global"),
    )

    branch_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_name = Column(String(255), nullable=False)
    branch_email = Column(String(255), nullable=True)
    contact_number = Column(String(10), nullable=False)
    address = Column(Text, nullable=False)
    status = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

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
