"""
Salary CRUD Operations - Database operations for salary management
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List
from datetime import datetime

from app.db.models.salary import EmployeeSalary, SalaryIncrement, SalarySlipHistory
from app.db.models.user import User
from app.schemas.salary_schema import (
    EmployeeSalaryCreate, EmployeeSalaryUpdate, 
    SalaryIncrementCreate
)
from app.utils.timezone import now_ist
import logging

logger = logging.getLogger(__name__)


# ==================== EMPLOYEE SALARY CRUD ====================

def create_employee_salary(db: Session, salary_data: EmployeeSalaryCreate) -> EmployeeSalary:
    """Create a new employee salary record"""
    # Check if salary record already exists for this user
    existing = db.query(EmployeeSalary).filter(
        EmployeeSalary.user_id == salary_data.user_id
    ).first()
    
    if existing:
        raise ValueError(f"Salary record already exists for user_id {salary_data.user_id}")
    
    db_salary = EmployeeSalary(**salary_data.model_dump())
    db.add(db_salary)
    db.commit()
    db.refresh(db_salary)
    
    logger.info(f"Created salary record for user_id: {salary_data.user_id}")
    return db_salary


def get_employee_salary(db: Session, user_id: int) -> Optional[EmployeeSalary]:
    """Get employee salary by user_id"""
    return db.query(EmployeeSalary).filter(
        EmployeeSalary.user_id == user_id,
        EmployeeSalary.is_active == True
    ).first()


def get_employee_salary_by_id(db: Session, salary_id: int) -> Optional[EmployeeSalary]:
    """Get employee salary by salary record id"""
    return db.query(EmployeeSalary).filter(
        EmployeeSalary.id == salary_id
    ).first()


def update_employee_salary(
    db: Session, 
    user_id: int, 
    salary_update: EmployeeSalaryUpdate
) -> Optional[EmployeeSalary]:
    """Update employee salary record"""
    salary = get_employee_salary(db, user_id)
    if not salary:
        return None
    
    update_data = salary_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(salary, key, value)
    
    salary.updated_at = now_ist()
    db.commit()
    db.refresh(salary)
    
    logger.info(f"Updated salary record for user_id: {user_id}")
    return salary


def delete_employee_salary(db: Session, user_id: int) -> bool:
    """Soft delete employee salary record"""
    salary = get_employee_salary(db, user_id)
    if not salary:
        return False
    
    salary.is_active = False
    salary.updated_at = now_ist()
    db.commit()
    
    logger.info(f"Deleted salary record for user_id: {user_id}")
    return True


def list_employee_salaries(
    db: Session, 
    department: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[EmployeeSalary]:
    """List all employee salaries with optional department filter"""
    query = db.query(EmployeeSalary).filter(EmployeeSalary.is_active == True)
    
    if department:
        # Join with User to filter by department
        query = query.join(User).filter(User.department == department)
    
    return query.offset(skip).limit(limit).all()


# ==================== SALARY INCREMENT CRUD ====================

def create_salary_increment(
    db: Session, 
    increment_data: SalaryIncrementCreate,
    approved_by: int
) -> SalaryIncrement:
    """Create a new salary increment record"""
    # Calculate percentage if not provided
    percentage = increment_data.increment_percentage
    if percentage is None and increment_data.previous_salary > 0:
        percentage = round(
            (increment_data.increment_amount / increment_data.previous_salary) * 100, 2
        )
    
    db_increment = SalaryIncrement(
        user_id=increment_data.user_id,
        previous_salary=increment_data.previous_salary,
        increment_amount=increment_data.increment_amount,
        new_salary=increment_data.new_salary,
        increment_percentage=percentage,
        effective_date=increment_data.effective_date,
        reason=increment_data.reason,
        approved_by=approved_by
    )
    
    db.add(db_increment)
    db.commit()
    db.refresh(db_increment)
    
    logger.info(f"Created increment record for user_id: {increment_data.user_id}")
    return db_increment


def get_salary_increment(db: Session, increment_id: int) -> Optional[SalaryIncrement]:
    """Get salary increment by id"""
    return db.query(SalaryIncrement).filter(
        SalaryIncrement.id == increment_id
    ).first()


def get_user_increments(db: Session, user_id: int) -> List[SalaryIncrement]:
    """Get all increments for a user"""
    return db.query(SalaryIncrement).filter(
        SalaryIncrement.user_id == user_id
    ).order_by(SalaryIncrement.effective_date.desc()).all()


def get_latest_increment(db: Session, user_id: int) -> Optional[SalaryIncrement]:
    """Get the latest increment for a user"""
    return db.query(SalaryIncrement).filter(
        SalaryIncrement.user_id == user_id
    ).order_by(SalaryIncrement.effective_date.desc()).first()


def update_increment_letter_sent(
    db: Session, 
    increment_id: int
) -> Optional[SalaryIncrement]:
    """Mark increment letter as sent"""
    increment = get_salary_increment(db, increment_id)
    if not increment:
        return None
    
    increment.letter_sent = True
    increment.letter_sent_at = now_ist()
    db.commit()
    db.refresh(increment)
    
    return increment


# ==================== SALARY SLIP HISTORY CRUD ====================

def create_salary_slip_history(
    db: Session,
    user_id: int,
    month: int,
    year: int,
    gross_salary: float,
    total_deductions: float,
    net_salary: float,
    generated_by: int
) -> SalarySlipHistory:
    """Create salary slip history record"""
    db_history = SalarySlipHistory(
        user_id=user_id,
        month=month,
        year=year,
        gross_salary=gross_salary,
        total_deductions=total_deductions,
        net_salary=net_salary,
        generated_by=generated_by
    )
    
    db.add(db_history)
    db.commit()
    db.refresh(db_history)
    
    return db_history


def get_salary_slip_history(
    db: Session, 
    user_id: int, 
    month: int, 
    year: int
) -> Optional[SalarySlipHistory]:
    """Get salary slip history for specific month/year"""
    return db.query(SalarySlipHistory).filter(
        and_(
            SalarySlipHistory.user_id == user_id,
            SalarySlipHistory.month == month,
            SalarySlipHistory.year == year
        )
    ).first()


def update_slip_email_sent(
    db: Session, 
    history_id: int
) -> Optional[SalarySlipHistory]:
    """Mark salary slip email as sent"""
    history = db.query(SalarySlipHistory).filter(
        SalarySlipHistory.id == history_id
    ).first()
    
    if not history:
        return None
    
    history.email_sent = True
    history.email_sent_at = now_ist()
    db.commit()
    db.refresh(history)
    
    return history


def get_user_salary_slip_history(
    db: Session, 
    user_id: int,
    year: Optional[int] = None
) -> List[SalarySlipHistory]:
    """Get all salary slip history for a user"""
    query = db.query(SalarySlipHistory).filter(
        SalarySlipHistory.user_id == user_id
    )
    
    if year:
        query = query.filter(SalarySlipHistory.year == year)
    
    return query.order_by(
        SalarySlipHistory.year.desc(),
        SalarySlipHistory.month.desc()
    ).all()
