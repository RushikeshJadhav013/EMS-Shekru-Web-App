from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class CompanySalaryStructure(Base):
    __tablename__ = "company_salary_structures"
    __table_args__ = (
        UniqueConstraint("company_id", "structure_name", name="uq_company_salary_structure_name"),
    )

    structure_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    structure_name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("super_admins.super_admin_id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    updated_by = Column(Integer, ForeignKey("super_admins.super_admin_id", ondelete="SET NULL"), nullable=True)

    components = relationship(
        "CompanySalaryStructureComponent",
        back_populates="structure",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CompanySalaryStructureComponent(Base):
    __tablename__ = "company_salary_structure_components"
    __table_args__ = (
        UniqueConstraint("structure_id", "component_code", name="uq_structure_component_code"),
    )

    component_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    structure_id = Column(
        Integer,
        ForeignKey("company_salary_structures.structure_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_code = Column(String(50), nullable=False)
    category = Column(String(20), nullable=False)  # EARNING or DEDUCTION
    calculation_type = Column(String(20), nullable=False)  # FIXED, PERCENTAGE, BALANCING
    percentage_base = Column(String(20), nullable=False, default="NONE")  # CTC, BASIC, GROSS, NONE
    percentage_value = Column(Numeric(12, 4), nullable=True)
    fixed_value = Column(Numeric(14, 2), nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    structure = relationship("CompanySalaryStructure", back_populates="components")
