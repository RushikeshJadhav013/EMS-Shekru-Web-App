from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from app.db.database import Base

class SuperAdmin(Base):
    __tablename__ = "super_admins"

    super_admin_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    contact_no = Column(String(20), nullable=False)

    # Additional fields
    gender = Column(String(50), nullable=True)
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