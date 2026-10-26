
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func

from app.db.database import Base


class Vendor(Base):
    __tablename__ = "vendors"

    vendor_id = Column(
        Integer,
        primary_key=True,
    )

    company_id = Column(
        Integer,
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    vendor_name = Column(String(150), nullable=False)
    contact_person = Column(String(100), nullable=True)
    email = Column(String(150), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(String(255), nullable=True)

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
