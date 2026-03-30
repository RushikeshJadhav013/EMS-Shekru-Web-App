from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, func
from app.db.database import Base


class Company(Base):
    __tablename__ = "companies"

    company_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_name = Column(String(255), nullable=False)
    company_email = Column(String(255), unique=True, index=True, nullable=False)
    contact_number = Column(String(10), nullable=False)
    address = Column(Text, nullable=False)
    gst_no = Column(String(50), nullable=True)
    company_logo = Column(String(1024), nullable=True)
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
