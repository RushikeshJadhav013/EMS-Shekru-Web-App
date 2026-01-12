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
    EmployeeSalaryCreate, EmployeeSalaryUpdate, EmployeeSalaryCTCCreate,
    EmployeeSalaryCTCUpdate, SalaryIncrementCreate, SalaryCalculationPreview
)
from app.services.salary_calculation_service import calculate_salary_from_ctc, SalaryCalculator
from app.utils.timezone import now_ist
import logging
import re

logger = logging.getLogger(__name__)


# ==================== EMPLOYEE SALARY CRUD ====================

def create_employee_salary_from_ctc(
    db: Session, 
    salary_data: EmployeeSalaryCTCCreate
) -> EmployeeSalary:
    """Create a new employee salary record from CTC with automatic calculations"""
    # Check if salary record already exists for this user
    existing = db.query(EmployeeSalary).filter(
        EmployeeSalary.user_id == salary_data.user_id
    ).first()
    
    if existing:
        raise ValueError(f"Salary record already exists for user_id {salary_data.user_id}")
    
    # Calculate salary components from CTC
    calculated_data = calculate_salary_from_ctc(
        annual_ctc=salary_data.annual_ctc,
        variable_pay_type=salary_data.variable_pay_type.value,
        variable_pay_value=salary_data.variable_pay_value,
        employer_pf_percentage=salary_data.employer_pf_percentage / 100.0,  # Convert percentage to decimal
        uan_number=salary_data.uan_number,
        bank_name=salary_data.bank_name,
        bank_account=salary_data.bank_account,
        ifsc_code=salary_data.ifsc_code,
        working_days_per_month=salary_data.working_days_per_month,
        payment_mode=salary_data.payment_mode
    )
    
    # Validate UAN uniqueness if provided
    if salary_data.uan_number:
        uan_digits = re.sub(r'[^0-9]', '', str(salary_data.uan_number))
        existing_uan = db.query(EmployeeSalary).filter(
            EmployeeSalary.uan_number == uan_digits,
            EmployeeSalary.is_active == True
        ).first()
        if existing_uan:
            raise ValueError(f"UAN '{uan_digits}' is already associated with another salary record")

    # Add user_id to calculated data
    calculated_data["user_id"] = salary_data.user_id
    # Normalize IFSC code to uppercase without surrounding whitespace (if present)
    if calculated_data.get("ifsc_code") is not None:
        calculated_data["ifsc_code"] = str(calculated_data["ifsc_code"]).strip().upper()
    
    # Create salary record
    db_salary = EmployeeSalary(**calculated_data)
    db.add(db_salary)
    db.commit()
    db.refresh(db_salary)
    
    logger.info(f"Created salary record from CTC {salary_data.annual_ctc} for user_id: {salary_data.user_id}")
    return db_salary


def create_employee_salary(db: Session, salary_data: EmployeeSalaryCreate) -> EmployeeSalary:
    """Create a new employee salary record (legacy manual entry)"""
    # Check if salary record already exists for this user
    existing = db.query(EmployeeSalary).filter(
        EmployeeSalary.user_id == salary_data.user_id
    ).first()
    
    if existing:
        raise ValueError(f"Salary record already exists for user_id {salary_data.user_id}")
    # Validate UAN uniqueness if provided
    if salary_data.uan_number:
        uan_digits = re.sub(r'[^0-9]', '', str(salary_data.uan_number))
        existing_uan = db.query(EmployeeSalary).filter(
            EmployeeSalary.uan_number == uan_digits,
            EmployeeSalary.is_active == True
        ).first()
        if existing_uan:
            raise ValueError(f"UAN '{uan_digits}' is already associated with another salary record")

    # Normalize IFSC code to uppercase without surrounding whitespace (if present)
    create_payload = salary_data.model_dump()
    if create_payload.get("ifsc_code") is not None:
        create_payload["ifsc_code"] = str(create_payload["ifsc_code"]).strip().upper()

    db_salary = EmployeeSalary(**create_payload)
    db.add(db_salary)
    db.commit()
    db.refresh(db_salary)
    
    logger.info(f"Created salary record for user_id: {salary_data.user_id}")
    return db_salary


def update_employee_salary_from_ctc(
    db: Session,
    user_id: int,
    ctc_update: EmployeeSalaryCTCUpdate
) -> Optional[EmployeeSalary]:
    """Update employee salary by recalculating from new CTC"""
    salary = get_employee_salary(db, user_id)
    if not salary:
        return None
    
    # Preserve existing non-calculated fields
    existing_data = {
        "uan_number": salary.uan_number,
        "bank_name": salary.bank_name,
        "bank_account": salary.bank_account,
        "ifsc_code": salary.ifsc_code,
        "working_days_per_month": salary.working_days_per_month,
        "payment_mode": salary.payment_mode
    }
    
    # Use existing variable pay settings if not provided
    vp_type = ctc_update.variable_pay_type.value if ctc_update.variable_pay_type else "none"
    vp_value = ctc_update.variable_pay_value if ctc_update.variable_pay_value is not None else 0.0
    
    # Use existing employer PF percentage if not provided
    employer_pf_pct = ctc_update.employer_pf_percentage / 100.0 if ctc_update.employer_pf_percentage is not None else None
    
    # Calculate new salary components
    calculated_data = calculate_salary_from_ctc(
        annual_ctc=ctc_update.annual_ctc,
        variable_pay_type=vp_type,
        variable_pay_value=vp_value,
        employer_pf_percentage=employer_pf_pct,
        **existing_data
    )
    
    # Update all calculated fields
    for key, value in calculated_data.items():
        setattr(salary, key, value)
    
    salary.updated_at = now_ist()
    db.commit()
    db.refresh(salary)
    
    logger.info(f"Updated salary record from CTC {ctc_update.annual_ctc} for user_id: {user_id}")
    return salary


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
    """Update employee salary record (only non-calculated fields)"""
    salary = get_employee_salary(db, user_id)
    if not salary:
        return None
    
    update_data = salary_update.model_dump(exclude_unset=True)
    
    # Handle variable pay update - recalculate if changed
    if 'variable_pay_type' in update_data or 'variable_pay_value' in update_data:
        current_ctc = salary.ctc_annual
        vp_type = update_data.get('variable_pay_type', 'none')
        vp_value = update_data.get('variable_pay_value', 0.0)
        
        # Recalculate variable pay component
        try:
            calculated_data = calculate_salary_from_ctc(
                annual_ctc=current_ctc,
                variable_pay_type=vp_type.value if hasattr(vp_type, 'value') else vp_type,
                variable_pay_value=vp_value,
                uan_number=salary.uan_number,
                bank_name=salary.bank_name,
                bank_account=salary.bank_account,
                ifsc_code=salary.ifsc_code,
                working_days_per_month=salary.working_days_per_month,
                payment_mode=salary.payment_mode
            )
            # Update only variable pay
            salary.variable_pay = calculated_data["variable_pay"]
        except Exception as e:
            logger.error(f"Error recalculating variable pay: {e}")
    
    # Update other allowed fields
    # If UAN is being updated, ensure uniqueness (exclude current user's salary record)
    if 'uan_number' in update_data and update_data.get('uan_number') is not None:
        uan_digits = re.sub(r'[^0-9]', '', str(update_data.get('uan_number')))
        existing_uan = db.query(EmployeeSalary).filter(
            EmployeeSalary.uan_number == uan_digits,
            EmployeeSalary.user_id != user_id,
            EmployeeSalary.is_active == True
        ).first()
        if existing_uan:
            raise ValueError(f"UAN '{uan_digits}' is already associated with another salary record")

    # Normalize IFSC in update payload if present
    if 'ifsc_code' in update_data and update_data.get('ifsc_code') is not None:
        update_data['ifsc_code'] = str(update_data['ifsc_code']).strip().upper()

    for key, value in update_data.items():
        if key not in ['variable_pay_type', 'variable_pay_value'] and value is not None:
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


def preview_salary_calculation(
    annual_ctc: float,
    variable_pay_type: str = "none",
    variable_pay_value: float = 0.0,
    employer_pf_percentage: float = None
) -> SalaryCalculationPreview:
    """Preview salary calculation without saving to database"""
    try:
        # Convert percentage to decimal if provided
        employer_pf_pct = employer_pf_percentage / 100.0 if employer_pf_percentage is not None else None
        
        components = SalaryCalculator.calculate_salary_components(
            annual_ctc, variable_pay_type, variable_pay_value, employer_pf_pct
        )
        
        return SalaryCalculationPreview(
            annual_ctc=annual_ctc,
            total_gross_annual=components["total_gross_annual"],
            basic_annual=components["basic_annual"],
            hra_annual=components["hra_annual"],
            special_allowance_annual=components["special_allowance_annual"],
            conveyance_annual=components["conveyance_annual"],
            medical_allowance_annual=components["medical_allowance_annual"],
            other_allowance_annual=components["other_allowance_annual"],
            professional_tax_annual=components["professional_tax_annual"],
            other_tax_annual=components["other_tax_annual"],
            employer_pf_annual=components["employer_pf_annual"],
            variable_pay_annual=components["variable_pay_annual"],
            
            # Monthly breakdown
            monthly_ctc=components["monthly_ctc"],
            monthly_gross=components["monthly_gross"],
            monthly_basic=round(components["basic_annual"] / 12, 2),
            monthly_hra=round(components["hra_annual"] / 12, 2),
            monthly_special_allowance=round(components["special_allowance_annual"] / 12, 2),
            monthly_conveyance=round(components["conveyance_annual"] / 12, 2),
            monthly_medical=round(components["medical_allowance_annual"] / 12, 2),
            monthly_other=round(components["other_allowance_annual"] / 12, 2),
            monthly_professional_tax=round(components["professional_tax_annual"] / 12, 2),
            monthly_other_tax=round(components["other_tax_annual"] / 12, 2),
            monthly_employer_pf=round(components["employer_pf_annual"] / 12, 2),
            monthly_variable_pay=components["monthly_variable_pay"],
            monthly_in_hand=components["monthly_in_hand"],
            
            # Summary
            total_earnings_annual=components["total_earnings_annual"],
            total_employee_deductions_annual=components["total_employee_deductions_annual"],
            total_employer_contributions_annual=components["total_employer_contributions_annual"],
            net_annual=components["net_annual"]
        )
    except ValueError as e:
        raise ValueError(f"Invalid CTC calculation: {str(e)}")


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
