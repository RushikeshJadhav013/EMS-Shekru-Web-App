"""
Salary Model - Employee Salary Information and Increment History
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.utils.timezone import now_ist


class EmployeeSalary(Base):
    """Employee salary structure with all components"""
    __tablename__ = "employee_salaries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, unique=True)
    
    # Basic salary components (Annual)
    basic_annual = Column(Float, default=0.0)
    hra_annual = Column(Float, default=0.0)
    special_allowance_annual = Column(Float, default=0.0)
    conveyance_annual = Column(Float, default=0.0)
    medical_allowance_annual = Column(Float, default=0.0)
    other_allowance_annual = Column(Float, default=0.0)
    
    # Deductions (Annual)
    professional_tax_annual = Column(Float, default=0.0)
    other_deduction_annual = Column(Float, default=0.0)
    pf_annual = Column(Float, default=0.0)  # Provident Fund
    
    # Additional info
    pan_number = Column(String(20), nullable=True)
    uan_number = Column(String(20), nullable=True)
    bank_name = Column(String(100), nullable=True)
    bank_account = Column(String(50), nullable=True)
    ifsc_code = Column(String(20), nullable=True)
    
    # Variable pay
    variable_pay = Column(Float, default=0.0)
    
    # Working days per month (default 22)
    working_days_per_month = Column(Integer, default=22)
    
    # Payment mode
    payment_mode = Column(String(50), default="Bank Transfer")
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)
    
    # Relationship
    user = relationship("User", backref="salary_info")
    
    @property
    def total_earnings_annual(self):
        return (self.basic_annual + self.hra_annual + self.special_allowance_annual +
                self.conveyance_annual + self.medical_allowance_annual + self.other_allowance_annual)
    
    @property
    def total_deductions_annual(self):
        return self.professional_tax_annual + self.other_deduction_annual + self.pf_annual
    
    @property
    def ctc_annual(self):
        return self.total_earnings_annual
    
    @property
    def monthly_ctc(self):
        return round(self.ctc_annual / 12, 2)
    
    @property
    def monthly_in_hand(self):
        return round((self.ctc_annual - self.total_deductions_annual) / 12, 2)


class SalaryIncrement(Base):
    """Salary increment history"""
    __tablename__ = "salary_increments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    
    # Increment details
    previous_salary = Column(Float, nullable=False)  # Monthly
    increment_amount = Column(Float, nullable=False)  # Monthly
    new_salary = Column(Float, nullable=False)  # Monthly
    increment_percentage = Column(Float, nullable=True)
    
    # Effective date
    effective_date = Column(DateTime, nullable=False)
    
    # Reason/remarks
    reason = Column(Text, nullable=True)
    
    # Approved by
    approved_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    
    # Letter sent status
    letter_sent = Column(Boolean, default=False)
    letter_sent_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=now_ist)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="increments")
    approver = relationship("User", foreign_keys=[approved_by])


class SalarySlipHistory(Base):
    """Track generated salary slips"""
    __tablename__ = "salary_slip_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    
    # Slip details
    month = Column(Integer, nullable=False)  # 1-12
    year = Column(Integer, nullable=False)
    
    # Amounts at time of generation
    gross_salary = Column(Float, nullable=False)
    total_deductions = Column(Float, nullable=False)
    net_salary = Column(Float, nullable=False)
    
    # Generation info
    generated_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    generated_at = Column(DateTime, default=now_ist)
    
    # Email sent status
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="salary_slips")
    generator = relationship("User", foreign_keys=[generated_by])
