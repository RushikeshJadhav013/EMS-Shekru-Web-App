"""
Salary CRUD Operations - Database operations for salary management
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import Optional, List, Union
from datetime import datetime

from app.db.models.salary import EmployeeSalary, EmployeeSalaryHistory, SalaryIncrement, SalarySlipHistory
from app.db.models.user import User
from app.db.models.notification import SalaryNotification
from app.utils.department_utils import department_token_regex_pattern
from app.schemas.salary_schema import (
    EmployeeSalaryCreate, EmployeeSalaryUpdate, EmployeeSalaryCTCCreate,
    EmployeeSalaryCTCUpdate, EmployeeSalaryManualFullUpdate, SalaryIncrementCreate, SalaryCalculationPreview
)
from app.services.salary_calculation_service import calculate_salary_from_ctc, SalaryCalculator
from app.utils.timezone import now_ist
import logging
import re
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)


# ==================== EMPLOYEE SALARY CRUD ====================
def _user_scope_filters(*, company_id: int | None, branch_id: int | None) -> list:
    clauses = []
    if company_id is not None:
        clauses.append(User.company_id == company_id)
    if branch_id is not None:
        clauses.append(User.branch_id == branch_id)
    return clauses


def _user_in_scope(db: Session, *, user_id: int, company_id: int | None, branch_id: int | None) -> bool:
    if company_id is None and branch_id is None:
        return True
    return (
        db.query(User.user_id)
        .filter(User.user_id == user_id, *_user_scope_filters(company_id=company_id, branch_id=branch_id))
        .first()
        is not None
    )



def _has_pf_account(pf_no: Optional[str]) -> bool:
    """PF can be generated only when PF account/member id exists."""
    if pf_no is None:
        return False
    val = str(pf_no).strip().upper()
    return val not in ("", "NA", "N/A")

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
    
    # PF input mode: either percentage or annual amount.
    pf_pct_provided = (
        "employer_pf_percentage" in salary_data.model_fields_set
        and salary_data.employer_pf_percentage is not None
    )
    pf_amount_provided = (
        "pf_annual" in salary_data.model_fields_set
        and salary_data.pf_annual is not None
    )
    if pf_pct_provided and pf_amount_provided:
        raise ValueError("Provide either employer_pf_percentage or pf_annual, not both.")
    if (pf_pct_provided or pf_amount_provided) and not _has_pf_account(salary_data.pf_no):
        raise ValueError("PF cannot be generated without PF account. Please provide a valid pf_no first.")

    employer_pf_pct = salary_data.employer_pf_percentage / 100.0 if pf_pct_provided else None

    calculated_data = calculate_salary_from_ctc(
        annual_ctc=salary_data.package_ctc_annual,
        variable_pay_type=salary_data.variable_pay_type.value,
        variable_pay_value=salary_data.variable_pay_value,
        employer_pf_percentage=employer_pf_pct,
        uan_number=salary_data.uan_number,
        pf_no=salary_data.pf_no,
        bank_name=salary_data.bank_name,
        bank_account=salary_data.bank_account,
        ifsc_code=salary_data.ifsc_code,
        working_days_per_month=salary_data.working_days_per_month,
        payment_mode=salary_data.payment_mode
    )
    # Apply selected PF mode to persisted field.
    if pf_amount_provided:
        calculated_data["pf_annual"] = float(salary_data.pf_annual)
    elif employer_pf_pct is None:
        calculated_data["pf_annual"] = None
    
    # Validate UAN uniqueness if provided
    if salary_data.uan_number:
        uan_digits = re.sub(r'[^0-9]', '', str(salary_data.uan_number))
        existing_uan = db.query(EmployeeSalary).filter(
            EmployeeSalary.uan_number == uan_digits,
            EmployeeSalary.is_active == True
        ).first()
        if existing_uan:
            raise ValueError(f"UAN '{uan_digits}' is already associated with another salary record")

    # Validate PF No uniqueness if provided (no duplication)
    if salary_data.pf_no:
        pf_normalized = str(salary_data.pf_no).strip().upper()
        existing_pf = db.query(EmployeeSalary).filter(
            EmployeeSalary.pf_no == pf_normalized,
            EmployeeSalary.is_active == True
        ).first()
        if existing_pf:
            raise ValueError(f"PF No '{pf_normalized}' is already associated with another salary record")

    # Validate bank account uniqueness within the same bank (if provided)
    if salary_data.bank_name and salary_data.bank_account:
        bank_name_norm = str(salary_data.bank_name).strip().lower()
        bank_account_norm = str(salary_data.bank_account).strip()
        existing_bank = (
            db.query(EmployeeSalary)
            .filter(
                EmployeeSalary.is_active == True,
                EmployeeSalary.bank_name.isnot(None),
                EmployeeSalary.bank_account.isnot(None),
                func.lower(EmployeeSalary.bank_name) == bank_name_norm,
                EmployeeSalary.bank_account == bank_account_norm,
            )
            .first()
        )
        if existing_bank:
            raise ValueError(
                f"Bank account '{bank_account_norm}' at bank '{salary_data.bank_name}' "
                "is already associated with another salary record"
            )

    # Add user_id to calculated data
    calculated_data["user_id"] = salary_data.user_id
    # Normalize IFSC code to uppercase without surrounding whitespace (if present)
    if calculated_data.get("ifsc_code") is not None:
        calculated_data["ifsc_code"] = str(calculated_data["ifsc_code"]).strip().upper()
    
    # Package CTC is required — store it for display
    calculated_data["package_ctc_annual"] = salary_data.package_ctc_annual
    # Other Tax is not accepted from the client; always persist 0.
    calculated_data["other_deduction_annual"] = 0.0
    
    # Create salary record
    db_salary = EmployeeSalary(**calculated_data)
    db.add(db_salary)
    db.commit()
    db.refresh(db_salary)
    
    logger.info(f"Created salary record from package CTC {salary_data.package_ctc_annual} for user_id: {salary_data.user_id}")
    return db_salary


def create_employee_salary(db: Session, salary_data: EmployeeSalaryCreate) -> EmployeeSalary:
    """Create a new employee salary record (legacy manual entry).

    Breakup is aligned with auto CTC calculation logic for consistency.
    """
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

    # Validate PF No uniqueness if provided (no duplication)
    if salary_data.pf_no:
        pf_normalized = str(salary_data.pf_no).strip().upper()
        existing_pf = db.query(EmployeeSalary).filter(
            EmployeeSalary.pf_no == pf_normalized,
            EmployeeSalary.is_active == True
        ).first()
        if existing_pf:
            raise ValueError(f"PF No '{pf_normalized}' is already associated with another salary record")

    # Validate bank account uniqueness within the same bank (if provided)
    if salary_data.bank_name and salary_data.bank_account:
        bank_name_norm = str(salary_data.bank_name).strip().lower()
        bank_account_norm = str(salary_data.bank_account).strip()
        existing_bank = (
            db.query(EmployeeSalary)
            .filter(
                EmployeeSalary.is_active == True,
                EmployeeSalary.bank_name.isnot(None),
                EmployeeSalary.bank_account.isnot(None),
                func.lower(EmployeeSalary.bank_name) == bank_name_norm,
                EmployeeSalary.bank_account == bank_account_norm,
            )
            .first()
        )
        if existing_bank:
            raise ValueError(
                f"Bank account '{bank_account_norm}' at bank '{salary_data.bank_name}' "
                "is already associated with another salary record"
            )

    # Normalize payload and align breakup with auto CTC calculation.
    create_payload = salary_data.model_dump()
    if create_payload.get("ifsc_code") is not None:
        create_payload["ifsc_code"] = str(create_payload["ifsc_code"]).strip().upper()

    pf_pct = create_payload.get("employer_pf_percentage")
    pf_amount = create_payload.get("pf_annual")
    if pf_pct is not None and pf_amount is not None:
        raise ValueError("Provide either employer_pf_percentage or pf_annual, not both.")
    if (pf_pct is not None or pf_amount is not None) and not _has_pf_account(create_payload.get("pf_no")):
        raise ValueError("PF cannot be generated without PF account. Please provide a valid pf_no first.")

    # Reconstruct offered package CTC from earnings side only so legacy create
    # follows the same breakup basis as the auto CTC endpoint.
    package_ctc_annual = (
        float(create_payload.get("basic_annual") or 0)
        + float(create_payload.get("hra_annual") or 0)
        + float(create_payload.get("special_allowance_annual") or 0)
        + float(create_payload.get("conveyance_annual") or 0)
        + float(create_payload.get("medical_allowance_annual") or 0)
        + float(create_payload.get("other_allowance_annual") or 0)
    )

    variable_pay_input = float(create_payload.get("variable_pay") or 0)
    calculated_data = calculate_salary_from_ctc(
        annual_ctc=package_ctc_annual,
        variable_pay_type="fixed" if variable_pay_input > 0 else "none",
        variable_pay_value=variable_pay_input,
        employer_pf_percentage=None,
        uan_number=create_payload.get("uan_number"),
        pf_no=create_payload.get("pf_no"),
        bank_name=create_payload.get("bank_name"),
        bank_account=create_payload.get("bank_account"),
        ifsc_code=create_payload.get("ifsc_code"),
        working_days_per_month=create_payload.get("working_days_per_month"),
        payment_mode=create_payload.get("payment_mode"),
    )

    # PF mode for legacy create: either annual amount or percentage of basic.
    if pf_amount is not None:
        calculated_data["pf_annual"] = float(pf_amount)
    elif pf_pct is not None:
        calculated_data["pf_annual"] = round(float(calculated_data.get("basic_annual") or 0) * float(pf_pct) / 100.0, 2)
    else:
        calculated_data["pf_annual"] = None

    calculated_data["user_id"] = salary_data.user_id
    calculated_data["package_ctc_annual"] = package_ctc_annual
    # Other Tax is not accepted from the client; always persist 0.
    calculated_data["other_deduction_annual"] = 0.0

    db_salary = EmployeeSalary(**calculated_data)
    db.add(db_salary)
    db.commit()
    db.refresh(db_salary)
    
    logger.info(f"Created salary record for user_id: {salary_data.user_id}")
    return db_salary


def _update_employee_salary_from_ctc(
    db: Session,
    user_id: int,
    ctc_update: EmployeeSalaryCTCUpdate,
    *,
    commit: bool,
) -> Optional[EmployeeSalary]:
    """Recalculate salary; optionally leave commit to the caller."""
    salary = get_employee_salary(db, user_id)
    if not salary:
        return None
    
    # Preserve existing non-calculated fields
    existing_data = {
        "uan_number": salary.uan_number,
        "pf_no": salary.pf_no,
        "bank_name": salary.bank_name,
        "bank_account": salary.bank_account,
        "ifsc_code": salary.ifsc_code,
        "working_days_per_month": salary.working_days_per_month,
        "payment_mode": salary.payment_mode
    }
    
    # Use existing variable pay settings if not provided
    vp_type = ctc_update.variable_pay_type.value if ctc_update.variable_pay_type else "none"
    vp_value = ctc_update.variable_pay_value if ctc_update.variable_pay_value is not None else 0.0
    
    # PF input mode: either percentage or annual amount.
    pf_pct_provided = ctc_update.employer_pf_percentage is not None
    pf_amount_provided = ctc_update.pf_annual is not None
    if pf_pct_provided and pf_amount_provided:
        raise ValueError("Provide either employer_pf_percentage or pf_annual, not both.")
    if (pf_pct_provided or pf_amount_provided) and not _has_pf_account(salary.pf_no):
        raise ValueError("PF cannot be generated without PF account. Please add a valid pf_no first.")

    employer_pf_pct = ctc_update.employer_pf_percentage / 100.0 if pf_pct_provided else None
    
    # Calculate new salary components using package CTC
    calculated_data = calculate_salary_from_ctc(
        annual_ctc=ctc_update.package_ctc_annual,
        variable_pay_type=vp_type,
        variable_pay_value=vp_value,
        employer_pf_percentage=employer_pf_pct,
        **existing_data
    )
    # Apply selected PF mode to persisted field.
    if pf_amount_provided:
        calculated_data["pf_annual"] = float(ctc_update.pf_annual)
    elif employer_pf_pct is None:
        calculated_data["pf_annual"] = None
    
    # Update all calculated fields
    for key, value in calculated_data.items():
        setattr(salary, key, value)
    
    # Update stored package CTC (required)
    salary.package_ctc_annual = ctc_update.package_ctc_annual
    # Other Tax is not accepted from the client; always persist 0.
    salary.other_deduction_annual = 0.0
    
    salary.updated_at = now_ist()
    if commit:
        db.commit()
        db.refresh(salary)
    
    logger.info(f"Updated salary record from package CTC {ctc_update.package_ctc_annual} for user_id: {user_id}")
    return salary


def update_employee_salary_from_ctc(
    db: Session,
    user_id: int,
    ctc_update: EmployeeSalaryCTCUpdate,
    changed_by: Optional[int] = None,
    changed_by_name: Optional[str] = None,
    changed_by_role: Optional[str] = None,
) -> Optional[EmployeeSalary]:
    """Public wrapper that snapshots prior salary to history and commits the salary update."""
    salary = get_employee_salary(db, user_id)
    if salary:
        latest_inc = (
            db.query(SalaryIncrement)
            .filter(SalaryIncrement.user_id == user_id)
            .order_by(SalaryIncrement.effective_date.desc(), SalaryIncrement.id.desc())
            .first()
        )
        effective_from = latest_inc.effective_date if latest_inc else salary.created_at
        now = now_ist()
        history = EmployeeSalaryHistory(
            user_id=salary.user_id,
            source_salary_id=salary.id,
            basic_annual=salary.basic_annual,
            hra_annual=salary.hra_annual,
            special_allowance_annual=salary.special_allowance_annual,
            conveyance_annual=salary.conveyance_annual,
            medical_allowance_annual=salary.medical_allowance_annual,
            other_allowance_annual=salary.other_allowance_annual,
            professional_tax_annual=salary.professional_tax_annual,
            other_deduction_annual=salary.other_deduction_annual,
            pf_annual=salary.pf_annual,
            package_ctc_annual=salary.package_ctc_annual,
            pan_number=salary.pan_number,
            uan_number=salary.uan_number,
            pf_no=salary.pf_no,
            bank_name=salary.bank_name,
            bank_account=salary.bank_account,
            ifsc_code=salary.ifsc_code,
            variable_pay=salary.variable_pay,
            working_days_per_month=salary.working_days_per_month,
            payment_mode=salary.payment_mode,
            is_active=salary.is_active,
            source_created_at=salary.created_at,
            source_updated_at=salary.updated_at,
            effective_from=effective_from,
            effective_to=now,
            change_type="update",
            reason="Direct CTC update",
            changed_by=changed_by,
            changed_by_name=changed_by_name,
            changed_by_role=changed_by_role,
        )
        db.add(history)
        db.flush()

    return _update_employee_salary_from_ctc(db, user_id, ctc_update, commit=True)



def get_employee_salary(
    db: Session,
    user_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[EmployeeSalary]:
    """Get employee salary by user_id"""
    q = db.query(EmployeeSalary).filter(
        EmployeeSalary.user_id == user_id,
        EmployeeSalary.is_active == True
    )
    if company_id is not None or branch_id is not None:
        q = q.join(User, EmployeeSalary.user_id == User.user_id).filter(
            *_user_scope_filters(company_id=company_id, branch_id=branch_id)
        )
    return q.first()


def get_employee_salary_by_id(db: Session, salary_id: int) -> Optional[EmployeeSalary]:
    """Get employee salary by salary record id"""
    return db.query(EmployeeSalary).filter(
        EmployeeSalary.id == salary_id
    ).first()


def get_salary_structure_for_period(
    db: Session,
    user_id: int,
    month: int,
    year: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[Union[EmployeeSalary, EmployeeSalaryHistory]]:
    """
    Get the salary structure (current EmployeeSalary or historical EmployeeSalaryHistory)
    effective during a specific (month, year) period.

    Logic:
    - Target period begins on datetime(year, month, 1).
    - If there are historical snapshots in EmployeeSalaryHistory whose effective_to > datetime(year, month, 1),
      the one with the earliest effective_to (ascending) that is after datetime(year, month, 1)
      was the active salary during that month.
    - If no snapshot has effective_to > datetime(year, month, 1), then all increments occurred
      prior to this month, meaning the current active EmployeeSalary applies.
    """
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return None

    period_start = datetime(year, month, 1)

    historical_snapshot = (
        db.query(EmployeeSalaryHistory)
        .filter(
            EmployeeSalaryHistory.user_id == user_id,
            EmployeeSalaryHistory.effective_to > period_start,
        )
        .order_by(EmployeeSalaryHistory.effective_to.asc(), EmployeeSalaryHistory.id.asc())
        .first()
    )
    if historical_snapshot:
        return historical_snapshot

    return get_employee_salary(db, user_id, company_id=company_id, branch_id=branch_id)



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
    pf_pct_provided = update_data.get("employer_pf_percentage") is not None
    pf_amount_provided = update_data.get("pf_annual") is not None
    if pf_pct_provided and pf_amount_provided:
        raise ValueError("Provide either employer_pf_percentage or pf_annual, not both.")
    
    # Handle variable pay update - recalculate if changed
    if 'variable_pay_type' in update_data or 'variable_pay_value' in update_data:
        # Use stored package CTC for recalculation
        current_ctc = salary.package_ctc_annual
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
    # If PF No is being updated, ensure uniqueness (exclude current user's salary record)
    if 'pf_no' in update_data and update_data.get('pf_no') is not None:
        pf_normalized = str(update_data.get('pf_no')).strip().upper()
        existing_pf = db.query(EmployeeSalary).filter(
            EmployeeSalary.pf_no == pf_normalized,
            EmployeeSalary.user_id != user_id,
            EmployeeSalary.is_active == True
        ).first()
        if existing_pf:
            raise ValueError(f"PF No '{pf_normalized}' is already associated with another salary record")

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

    # Business rule: PF cannot be generated/stored without PF account.
    effective_pf_no = update_data.get("pf_no", salary.pf_no)
    if pf_pct_provided and not _has_pf_account(effective_pf_no):
        raise ValueError("PF cannot be generated without PF account. Please add a valid pf_no first.")
    if pf_pct_provided:
        # In manual update flow, PF % is applied on current Basic annual.
        update_data["pf_annual"] = round(float(salary.basic_annual or 0) * float(update_data["employer_pf_percentage"]) / 100.0, 2)
    if not _has_pf_account(effective_pf_no):
        update_data["pf_annual"] = None

    # Validate bank account uniqueness within the same bank on update (if changing bank or account)
    if ('bank_name' in update_data and update_data.get('bank_name') is not None) or (
        'bank_account' in update_data and update_data.get('bank_account') is not None
    ):
        effective_bank_name = update_data.get('bank_name', salary.bank_name)
        effective_bank_account = update_data.get('bank_account', salary.bank_account)
        if effective_bank_name and effective_bank_account:
            bank_name_norm = str(effective_bank_name).strip().lower()
            bank_account_norm = str(effective_bank_account).strip()
            existing_bank = (
                db.query(EmployeeSalary)
                .filter(
                    EmployeeSalary.user_id != user_id,
                    EmployeeSalary.is_active == True,
                    EmployeeSalary.bank_name.isnot(None),
                    EmployeeSalary.bank_account.isnot(None),
                    func.lower(EmployeeSalary.bank_name) == bank_name_norm,
                    EmployeeSalary.bank_account == bank_account_norm,
                )
                .first()
            )
            if existing_bank:
                raise ValueError(
                    f"Bank account '{bank_account_norm}' at bank '{effective_bank_name}' "
                    "is already associated with another salary record"
                )

    for key, value in update_data.items():
        if key == "pf_annual" and value is None:
            setattr(salary, key, None)
        elif key not in ['variable_pay_type', 'variable_pay_value', 'employer_pf_percentage'] and value is not None:
            setattr(salary, key, value)

    # Other Tax is not accepted from the client; always persist 0.
    salary.other_deduction_annual = 0.0
    
    salary.updated_at = now_ist()
    db.commit()
    db.refresh(salary)
    
    logger.info(f"Updated salary record for user_id: {user_id}")
    return salary


def update_employee_salary_manual_full(
    db: Session,
    user_id: int,
    salary_update: EmployeeSalaryManualFullUpdate
) -> Optional[EmployeeSalary]:
    """Manual full-edit update: directly update salary components and related fields."""
    salary = get_employee_salary(db, user_id)
    if not salary:
        return None

    update_data = salary_update.model_dump(exclude_unset=True)
    pf_pct_provided = update_data.get("employer_pf_percentage") is not None
    pf_amount_provided = update_data.get("pf_annual") is not None
    if pf_pct_provided and pf_amount_provided:
        raise ValueError("Provide either employer_pf_percentage or pf_annual, not both.")

    # PF No uniqueness check (exclude current record)
    if 'pf_no' in update_data and update_data.get('pf_no') is not None:
        pf_normalized = str(update_data.get('pf_no')).strip().upper()
        existing_pf = db.query(EmployeeSalary).filter(
            EmployeeSalary.pf_no == pf_normalized,
            EmployeeSalary.user_id != user_id,
            EmployeeSalary.is_active == True
        ).first()
        if existing_pf:
            raise ValueError(f"PF No '{pf_normalized}' is already associated with another salary record")

    # UAN uniqueness check (exclude current record)
    if 'uan_number' in update_data and update_data.get('uan_number') is not None:
        uan_digits = re.sub(r'[^0-9]', '', str(update_data.get('uan_number')))
        existing_uan = db.query(EmployeeSalary).filter(
            EmployeeSalary.uan_number == uan_digits,
            EmployeeSalary.user_id != user_id,
            EmployeeSalary.is_active == True
        ).first()
        if existing_uan:
            raise ValueError(f"UAN '{uan_digits}' is already associated with another salary record")

    # Normalize IFSC
    if 'ifsc_code' in update_data and update_data.get('ifsc_code') is not None:
        update_data['ifsc_code'] = str(update_data['ifsc_code']).strip().upper()

    # Bank account uniqueness check if either bank/account is being changed
    if ('bank_name' in update_data and update_data.get('bank_name') is not None) or (
        'bank_account' in update_data and update_data.get('bank_account') is not None
    ):
        effective_bank_name = update_data.get('bank_name', salary.bank_name)
        effective_bank_account = update_data.get('bank_account', salary.bank_account)
        if effective_bank_name and effective_bank_account:
            bank_name_norm = str(effective_bank_name).strip().lower()
            bank_account_norm = str(effective_bank_account).strip()
            existing_bank = (
                db.query(EmployeeSalary)
                .filter(
                    EmployeeSalary.user_id != user_id,
                    EmployeeSalary.is_active == True,
                    EmployeeSalary.bank_name.isnot(None),
                    EmployeeSalary.bank_account.isnot(None),
                    func.lower(EmployeeSalary.bank_name) == bank_name_norm,
                    EmployeeSalary.bank_account == bank_account_norm,
                )
                .first()
            )
            if existing_bank:
                raise ValueError(
                    f"Bank account '{bank_account_norm}' at bank '{effective_bank_name}' "
                    "is already associated with another salary record"
                )

    # PF business rule: without PF account, PF amount must be null.
    effective_pf_no = update_data.get("pf_no", salary.pf_no)
    if pf_pct_provided and not _has_pf_account(effective_pf_no):
        raise ValueError("PF cannot be generated without PF account. Please add a valid pf_no first.")
    if pf_pct_provided:
        effective_basic = float(update_data.get("basic_annual", salary.basic_annual) or 0)
        update_data["pf_annual"] = round(effective_basic * float(update_data["employer_pf_percentage"]) / 100.0, 2)
    if not _has_pf_account(effective_pf_no):
        update_data["pf_annual"] = None

    for key, value in update_data.items():
        if key == "employer_pf_percentage":
            continue
        if value is not None:
            setattr(salary, key, value)
        elif key in ("pf_annual", "pf_no"):
            # allow explicit clearing for PF fields
            setattr(salary, key, None)

    # Other Tax is not accepted from the client; always persist 0.
    salary.other_deduction_annual = 0.0

    # Recompute package CTC aligned with other salary APIs (earnings-side basis).
    salary.package_ctc_annual = (
        float(salary.basic_annual or 0)
        + float(salary.hra_annual or 0)
        + float(salary.special_allowance_annual or 0)
        + float(salary.conveyance_annual or 0)
        + float(salary.medical_allowance_annual or 0)
        + float(salary.other_allowance_annual or 0)
    )

    salary.updated_at = now_ist()
    db.commit()
    db.refresh(salary)

    logger.info(f"Manually full-updated salary record for user_id: {user_id}")
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
    departments: Optional[List[str]] = None,
    skip: int = 0, 
    limit: int = 100,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> List[EmployeeSalary]:
    """List all employee salaries (including inactive) with optional department filter(s)."""
    query = db.query(EmployeeSalary)
    joined_user = False

    if company_id is not None or branch_id is not None:
        query = query.join(User, EmployeeSalary.user_id == User.user_id).filter(
            *_user_scope_filters(company_id=company_id, branch_id=branch_id)
        )
        joined_user = True
    
    if departments:
        # Join with User to filter by department tokens. Supports users with multiple comma-separated departments.
        patterns = [department_token_regex_pattern(d) for d in departments]
        dept_filters = [User.department.op("RLIKE")(pat) for pat in patterns]
        if not joined_user:
            query = query.join(User)
        query = query.filter(User.department.isnot(None), or_(*dept_filters))
    
    return query.offset(skip).limit(limit).all()


def preview_salary_calculation(
    package_ctc_annual: float,
    variable_pay_type: str = "none",
    variable_pay_value: float = 0.0,
    employer_pf_percentage: float = None
) -> SalaryCalculationPreview:
    """Preview salary calculation without saving to database"""
    try:
        # Convert percentage to decimal if provided
        employer_pf_pct = employer_pf_percentage / 100.0 if employer_pf_percentage is not None else None
        
        components = SalaryCalculator.calculate_salary_components(
            package_ctc_annual, variable_pay_type, variable_pay_value, employer_pf_pct
        )
        
        return SalaryCalculationPreview(
            package_ctc_annual=package_ctc_annual,
            total_gross_annual=components["total_gross_annual"],
            basic_annual=components["basic_annual"],
            hra_annual=components["hra_annual"],
            special_allowance_annual=components["special_allowance_annual"],
            conveyance_annual=components["conveyance_annual"],
            medical_allowance_annual=components["medical_allowance_annual"],
            other_allowance_annual=components["other_allowance_annual"],
            professional_tax_annual=components["professional_tax_annual"],
            # Other Tax is hidden from salary JSON and is always 0 internally.
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
    approved_by: int,
    approved_by_name: Optional[str] = None,
    approved_by_role: Optional[str] = None,
) -> SalaryIncrement:
    """Record the previous salary, update the current structure and add the increment atomically."""
    try:
        # Lock the current salary row so concurrent increments cannot snapshot the same version.
        current_salary = (
            db.query(EmployeeSalary)
            .filter(EmployeeSalary.user_id == increment_data.user_id, EmployeeSalary.is_active.is_(True))
            .with_for_update()
            .first()
        )
        if not current_salary:
            raise ValueError(
                f"No salary record found for user_id {increment_data.user_id}. "
                "Please create a salary record before applying increment."
            )

        # Validation: Joining date check
        user = db.query(User).filter(User.user_id == increment_data.user_id).first()
        if user and user.joining_date:
            inc_date = (
                increment_data.effective_date.date()
                if isinstance(increment_data.effective_date, datetime)
                else increment_data.effective_date
            )
            user_joining = (
                user.joining_date.date()
                if isinstance(user.joining_date, datetime)
                else user.joining_date
            )
            if inc_date < user_joining:
                raise ValueError(
                    f"Increment effective date ({inc_date.strftime('%d-%m-%Y')}) "
                    f"cannot be before employee joining date ({user_joining.strftime('%d-%m-%Y')})"
                )

        # Validation: Chronological order check against latest increment
        latest_inc = (
            db.query(SalaryIncrement)
            .filter(SalaryIncrement.user_id == increment_data.user_id)
            .order_by(SalaryIncrement.effective_date.desc(), SalaryIncrement.id.desc())
            .first()
        )
        if latest_inc and increment_data.effective_date <= latest_inc.effective_date:
            raise ValueError(
                f"Increment effective date ({increment_data.effective_date.strftime('%d-%m-%Y')}) "
                f"must be after the previous increment date ({latest_inc.effective_date.strftime('%d-%m-%Y')})"
            )

        previous_ctc = float(current_salary.ctc_annual)
        if increment_data.increment_ctc_annual is not None:
            increment_ctc = float(increment_data.increment_ctc_annual)
            increment_percentage = round((increment_ctc / previous_ctc) * 100, 2) if previous_ctc > 0 else 0
        else:
            increment_percentage = float(increment_data.increment_percentage)
            increment_ctc = round((previous_ctc * increment_percentage) / 100, 2)
        new_ctc = previous_ctc + increment_ctc

        # Validation: Minimum CTC check
        min_ctc = SalaryCalculator.get_minimum_ctc()
        if new_ctc < min_ctc:
            raise ValueError(f"New CTC ₹{new_ctc:,.2f} cannot be less than minimum allowed CTC ₹{min_ctc:,.2f}")

        # Determine effective_from for historical snapshot:
        # If there was a previous increment, the previous structure started then; otherwise when created.
        effective_from = latest_inc.effective_date if latest_inc else current_salary.created_at

        # Snapshot every persisted EmployeeSalary field before any mutation.
        history = EmployeeSalaryHistory(
            user_id=current_salary.user_id,
            source_salary_id=current_salary.id,
            basic_annual=current_salary.basic_annual,
            hra_annual=current_salary.hra_annual,
            special_allowance_annual=current_salary.special_allowance_annual,
            conveyance_annual=current_salary.conveyance_annual,
            medical_allowance_annual=current_salary.medical_allowance_annual,
            other_allowance_annual=current_salary.other_allowance_annual,
            professional_tax_annual=current_salary.professional_tax_annual,
            other_deduction_annual=current_salary.other_deduction_annual,
            pf_annual=current_salary.pf_annual,
            package_ctc_annual=current_salary.package_ctc_annual,
            pan_number=current_salary.pan_number,
            uan_number=current_salary.uan_number,
            pf_no=current_salary.pf_no,
            bank_name=current_salary.bank_name,
            bank_account=current_salary.bank_account,
            ifsc_code=current_salary.ifsc_code,
            variable_pay=current_salary.variable_pay,
            working_days_per_month=current_salary.working_days_per_month,
            payment_mode=current_salary.payment_mode,
            is_active=current_salary.is_active,
            source_created_at=current_salary.created_at,
            source_updated_at=current_salary.updated_at,
            effective_from=effective_from,
            effective_to=increment_data.effective_date,
            change_type="increment",
            reason=increment_data.reason,
            changed_by=approved_by,
            changed_by_name=approved_by_name,
            changed_by_role=approved_by_role,
        )
        db.add(history)
        db.flush()

        from app.schemas.salary_schema import EmployeeSalaryCTCUpdate
        ctc_update = EmployeeSalaryCTCUpdate(
            package_ctc_annual=new_ctc,
            variable_pay_type=increment_data.variable_pay_type,
            variable_pay_value=increment_data.variable_pay_value,
        )
        updated_salary = _update_employee_salary_from_ctc(
            db, increment_data.user_id, ctc_update, commit=False
        )
        if not updated_salary:
            raise ValueError(f"Failed to update salary for user_id {increment_data.user_id}")

        previous_monthly = (Decimal(str(previous_ctc)) / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        increment_monthly = (Decimal(str(increment_ctc)) / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        new_monthly = (Decimal(str(new_ctc)) / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        db_increment = SalaryIncrement(
            user_id=increment_data.user_id,
            previous_ctc_annual=previous_ctc,
            increment_ctc_annual=increment_ctc,
            new_ctc_annual=new_ctc,
            increment_percentage=increment_percentage,
            previous_salary=previous_monthly,
            increment_amount=increment_monthly,
            new_salary=new_monthly,
            effective_date=increment_data.effective_date,
            effective_month=increment_data.effective_date.month,
            effective_year=increment_data.effective_date.year,
            reason=increment_data.reason,
            approved_by=approved_by,
            approved_by_name=approved_by_name,
            approved_by_role=approved_by_role,
            salary_history_id=history.id,
        )
        db.add(db_increment)
        db.commit()
        db.refresh(db_increment)
        logger.info(
            "Created increment record for user_id=%s increment_id=%s history_id=%s previous_ctc=%s new_ctc=%s approved_by=%s role=%s",
            increment_data.user_id, db_increment.id, history.id, previous_ctc, new_ctc, approved_by_name, approved_by_role
        )
        return db_increment
    except Exception:
        db.rollback()
        raise


def get_salary_history(
    db: Session, user_id: int, *, company_id: int | None = None, branch_id: int | None = None
) -> List[EmployeeSalaryHistory]:
    """Return salary snapshots newest first, scoped to the employee's tenant."""
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return []
    return (
        db.query(EmployeeSalaryHistory)
        .filter(EmployeeSalaryHistory.user_id == user_id)
        .order_by(EmployeeSalaryHistory.effective_to.desc(), EmployeeSalaryHistory.id.desc())
        .all()
    )


def get_salary_increment(
    db: Session,
    increment_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[SalaryIncrement]:
    """Get salary increment by id"""
    q = db.query(SalaryIncrement).filter(SalaryIncrement.id == increment_id)
    if company_id is not None or branch_id is not None:
        q = q.join(User, SalaryIncrement.user_id == User.user_id).filter(
            *_user_scope_filters(company_id=company_id, branch_id=branch_id)
        )
    return q.first()


def get_user_increments(
    db: Session,
    user_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> List[SalaryIncrement]:
    """Get all increments for a user"""
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return []
    return (
        db.query(SalaryIncrement)
        .filter(SalaryIncrement.user_id == user_id)
        .order_by(SalaryIncrement.effective_date.desc())
        .all()
    )


def get_latest_increment(
    db: Session,
    user_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[SalaryIncrement]:
    """Get the latest increment for a user"""
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return None
    return (
        db.query(SalaryIncrement)
        .filter(SalaryIncrement.user_id == user_id)
        .order_by(SalaryIncrement.effective_date.desc())
        .first()
    )


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
    generated_by: int,
    *,
    basic: Optional[float] = None,
    hra: Optional[float] = None,
    special_allowance: Optional[float] = None,
    conveyance: Optional[float] = None,
    medical_allowance: Optional[float] = None,
    other_allowance: Optional[float] = None,
    professional_tax: Optional[float] = None,
    pf: Optional[float] = None,
    variable_pay: Optional[float] = 0.0,
    salary_history_id: Optional[int] = None,
    optional_deduction_1_label: Optional[str] = None,
    optional_deduction_1_amount: Optional[float] = None,
    optional_deduction_2_label: Optional[str] = None,
    optional_deduction_2_amount: Optional[float] = None,
    optional_deduction_3_label: Optional[str] = None,
    optional_deduction_3_amount: Optional[float] = None,
    optional_deduction_4_label: Optional[str] = None,
    optional_deduction_4_amount: Optional[float] = None,
    manual_leave_days: float = 0.0,
    manual_leave_amount: float = 0.0,
) -> SalarySlipHistory:
    """
    Upsert salary slip history for (user_id, month, year).

    Updates the latest existing row when present so repeated finalize for the
    same month does not create unbounded duplicates. Legacy totals on older
    duplicate rows are left untouched.
    """
    existing = (
        db.query(SalarySlipHistory)
        .filter(
            SalarySlipHistory.user_id == user_id,
            SalarySlipHistory.month == month,
            SalarySlipHistory.year == year,
        )
        .order_by(SalarySlipHistory.id.desc())
        .first()
    )

    breakdown = {
        "gross_salary": float(gross_salary),
        "total_deductions": float(total_deductions),
        "net_salary": float(net_salary),
        "optional_deduction_1_label": optional_deduction_1_label,
        "optional_deduction_1_amount": optional_deduction_1_amount,
        "optional_deduction_2_label": optional_deduction_2_label,
        "optional_deduction_2_amount": optional_deduction_2_amount,
        "optional_deduction_3_label": optional_deduction_3_label,
        "optional_deduction_3_amount": optional_deduction_3_amount,
        "optional_deduction_4_label": optional_deduction_4_label,
        "optional_deduction_4_amount": optional_deduction_4_amount,
        "manual_leave_days": float(manual_leave_days or 0.0),
        "manual_leave_amount": float(manual_leave_amount or 0.0),
        "generated_by": generated_by,
        "generated_at": now_ist(),
    }

    if basic is not None:
        breakdown["basic"] = float(basic)
    if hra is not None:
        breakdown["hra"] = float(hra)
    if special_allowance is not None:
        breakdown["special_allowance"] = float(special_allowance)
    if conveyance is not None:
        breakdown["conveyance"] = float(conveyance)
    if medical_allowance is not None:
        breakdown["medical_allowance"] = float(medical_allowance)
    if other_allowance is not None:
        breakdown["other_allowance"] = float(other_allowance)
    if professional_tax is not None:
        breakdown["professional_tax"] = float(professional_tax)
    if pf is not None:
        breakdown["pf"] = float(pf)
    if variable_pay is not None:
        breakdown["variable_pay"] = float(variable_pay)
    if salary_history_id is not None:
        breakdown["salary_history_id"] = salary_history_id

    if existing:
        for key, value in breakdown.items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing

    db_history = SalarySlipHistory(
        user_id=user_id,
        month=month,
        year=year,
        **breakdown,
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
    """Get latest salary slip history for specific month/year"""
    return (
        db.query(SalarySlipHistory)
        .filter(
            and_(
                SalarySlipHistory.user_id == user_id,
                SalarySlipHistory.month == month,
                SalarySlipHistory.year == year,
            )
        )
        .order_by(SalarySlipHistory.id.desc())
        .first()
    )


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
    year: Optional[int] = None,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> List[SalarySlipHistory]:
    """Get all salary slip history for a user"""
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return []
    query = db.query(SalarySlipHistory).filter(
        SalarySlipHistory.user_id == user_id
    )
    
    if year:
        query = query.filter(SalarySlipHistory.year == year)
    
    return query.order_by(
        SalarySlipHistory.year.desc(),
        SalarySlipHistory.month.desc()
    ).all()


# ==================== SALARY NOTIFICATION CRUD ====================

def create_salary_notification(
    db: Session,
    user_id: int,
    notification_type: str,
    title: str,
    message: str
) -> SalaryNotification:
    """Create a salary notification for a user"""
    db_notification = SalaryNotification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message
    )
    
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    
    logger.info(f"Created salary notification for user_id: {user_id}, type: {notification_type}")
    return db_notification


def list_salary_notifications(
    db: Session,
    user_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> List[SalaryNotification]:
    """Get all salary notifications for a user, ordered by most recent first"""
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return []
    return (
        db.query(SalaryNotification)
        .filter(SalaryNotification.user_id == user_id)
        .order_by(SalaryNotification.created_at.desc())
        .all()
    )


def mark_salary_notification_as_read(
    db: Session, 
    notification_id: int, 
    user_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> Optional[SalaryNotification]:
    """Mark a salary notification as read for a specific user"""
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return None
    notification = db.query(SalaryNotification).filter(
        SalaryNotification.notification_id == notification_id,
        SalaryNotification.user_id == user_id
    ).first()
    
    if not notification:
        return None
    
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    
    logger.info(f"Marked salary notification {notification_id} as read for user_id: {user_id}")
    return notification


def get_unread_salary_notifications_count(
    db: Session,
    user_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> int:
    """Get count of unread salary notifications for a user"""
    if not _user_in_scope(db, user_id=user_id, company_id=company_id, branch_id=branch_id):
        return 0
    return db.query(SalaryNotification).filter(
        SalaryNotification.user_id == user_id,
        SalaryNotification.is_read == False
    ).count()
