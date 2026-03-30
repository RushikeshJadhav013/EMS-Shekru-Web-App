"""
Salary Routes - API endpoints for salary slip, increment letter, and salary annexure
Admin/HR only access with role-based permissions
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List, Literal, Tuple
from datetime import datetime
import logging
import traceback

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.department import Department
from app.db.models.salary import EmployeeSalary, SalaryIncrement
from app.dependencies import get_current_user, require_roles
from app.enums import RoleEnum
from app.schemas.salary_schema import (
    EmployeeSalaryCreate, EmployeeSalaryUpdate, EmployeeSalaryManualFullUpdate, EmployeeSalaryOut,
    EmployeeSalaryCTCCreate, EmployeeSalaryCTCUpdate, SalaryCalculationPreview,
    SalaryIncrementCreate, SalaryIncrementOut,
    SalarySlipRequest, IncrementLetterRequest, SalaryAnnexureRequest,
    EmailResponse, VariablePayType, SalaryNotificationOut,
    EmployeeSalaryStatusUpdate,
)
from app.crud.salary_crud import (
    create_employee_salary, create_employee_salary_from_ctc, get_employee_salary, 
    update_employee_salary, update_employee_salary_manual_full, update_employee_salary_from_ctc, delete_employee_salary, 
    list_employee_salaries, preview_salary_calculation,
    create_salary_increment, get_salary_increment, get_user_increments,
    get_latest_increment, update_increment_letter_sent,
    create_salary_slip_history, get_salary_slip_history, update_slip_email_sent,
    get_user_salary_slip_history,
    create_salary_notification, list_salary_notifications,
    mark_salary_notification_as_read, get_unread_salary_notifications_count
)
from app.services.salary_pdf_service import (
    generate_salary_slip_pdf, generate_salary_annexure_pdf,
    generate_increment_letter_pdf, generate_offer_letter_pdf
)
from app.services.salary_email_service import (
    send_salary_slip_email, send_increment_letter_email, send_salary_annexure_email
)
from app.services.salary_calculation_service import SalaryCalculator
from app.crud.user_crud import get_user
from app.utils.department_utils import department_tokens_lower
from app.utils.timezone import now_ist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/salary", tags=["Salary Management"])


def _enforce_hr_non_privileged_target(current_user: User, target_user: User, action: str) -> None:
    """HR can manage salary only for non-Admin and non-HR users."""
    # Allow HR to view/read their own salary record.
    # For other actions (create/update/status), HR is still restricted.
    if current_user.user_id == target_user.user_id and action.startswith("view"):
        return
    if current_user.role == RoleEnum.HR and target_user.role in (RoleEnum.ADMIN, RoleEnum.HR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"HR can only {action} for non-Admin and non-HR users",
        )


# Helper to attach variable pay info from the current salary record
def _increment_to_out(increment: SalaryIncrement, db: Session) -> SalaryIncrementOut:
    """
    Build SalaryIncrementOut and map variable_pay_value from the employee's current salary.
    Note: variable_pay_type is left as None because it is not stored per-increment.
    """
    salary = get_employee_salary(db, increment.user_id)
    variable_pay_value = getattr(salary, "variable_pay", None) if salary is not None else None

    return SalaryIncrementOut(
        id=increment.id,
        user_id=increment.user_id,
        # variable_pay_type is intentionally omitted from response mapping
        variable_pay_value=variable_pay_value,
        previous_salary=float(increment.previous_salary),
        increment_amount=float(increment.increment_amount),
        new_salary=float(increment.new_salary),
        previous_ctc_annual=increment.previous_ctc_annual,
        increment_ctc_annual=increment.increment_ctc_annual,
        new_ctc_annual=increment.new_ctc_annual,
        increment_percentage=increment.increment_percentage,
        effective_date=increment.effective_date,
        reason=increment.reason,
        approved_by=increment.approved_by,
        letter_sent=increment.letter_sent,
        letter_sent_at=increment.letter_sent_at,
        created_at=increment.created_at,
    )


# ==================== CTC-BASED PAYROLL ENDPOINTS ====================

# @router.post("/calculate-preview", response_model=SalaryCalculationPreview)
# def preview_ctc_calculation(
#     package_ctc_annual: float = Query(..., gt=0, description="Package Annual CTC amount"),
#     variable_pay_type: VariablePayType = Query(default=VariablePayType.NONE),
#     variable_pay_value: float = Query(default=0.0, ge=0),
#     employer_pf_percentage: float = Query(default=12.0, ge=0, le=100, description="Employer PF percentage"),
#     current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
# ):
#     """
#     Preview salary calculation from CTC without saving.
#     Shows breakdown of all components for HR review.
#     """
#     try:
#         return preview_salary_calculation(
#             package_ctc_annual=package_ctc_annual,
#             variable_pay_type=variable_pay_type.value,
#             variable_pay_value=variable_pay_value,
#             employer_pf_percentage=employer_pf_percentage
#         )
#     except ValueError as e:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=str(e)
#         )


# @router.get("/minimum-ctc")
# def get_minimum_ctc(
#     current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
# ):
#     """Get minimum CTC required for fixed components"""
#     min_ctc = SalaryCalculator.get_minimum_ctc()
#     return {
#         "minimum_ctc": min_ctc,
#         "formatted": f"₹{min_ctc:,.2f}",
#         "components": {
#             "medical_annual": SalaryCalculator.MEDICAL_ALLOWANCE_ANNUAL,
#             "conveyance_annual": SalaryCalculator.CONVEYANCE_ALLOWANCE_ANNUAL,
#             "other_annual": SalaryCalculator.OTHER_ALLOWANCE_ANNUAL,
#             "basic_percentage": f"{SalaryCalculator.BASIC_PERCENTAGE * 100}%",
#             "hra_percentage": f"{SalaryCalculator.HRA_PERCENTAGE * 100}% of Basic"
#         }
#     }


@router.post("/employee/from-ctc", response_model=EmployeeSalaryOut, status_code=status.HTTP_201_CREATED)
def create_salary_from_ctc(
    salary_data: EmployeeSalaryCTCCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Create salary record from Annual CTC with automatic component calculation.
    HR enters only CTC amount and system calculates all components automatically.
    """
    # Verify user exists
    user = get_user(db, salary_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {salary_data.user_id} not found"
        )
    _enforce_hr_non_privileged_target(current_user, user, "create salary")
    
    try:
        salary = create_employee_salary_from_ctc(db, salary_data)
        return _salary_to_response(salary)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating salary from CTC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating salary record from CTC"
        )


@router.put("/employee/{user_id}/update-ctc", response_model=EmployeeSalaryOut)
def update_salary_from_ctc(
    user_id: int,
    ctc_update: EmployeeSalaryCTCUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Update salary by changing CTC - recalculates all components automatically.
    """
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    _enforce_hr_non_privileged_target(current_user, user, "update salary")

    try:
        salary = update_employee_salary_from_ctc(db, user_id, ctc_update)
        if not salary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salary record not found for this employee"
            )
        return _salary_to_response(salary)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating salary from CTC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating salary from CTC"
        )


# ==================== EMPLOYEE SALARY CRUD ENDPOINTS ====================

@router.post("/employee", response_model=EmployeeSalaryOut, status_code=status.HTTP_201_CREATED)
def create_salary_record(
    salary_data: EmployeeSalaryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Create salary record manually (legacy method).
    Use /employee/from-ctc for automatic calculation instead.
    """
    # Verify user exists
    user = get_user(db, salary_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {salary_data.user_id} not found"
        )
    _enforce_hr_non_privileged_target(current_user, user, "create salary")
    
    try:
        salary = create_employee_salary(db, salary_data)
        return _salary_to_response(salary)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating salary record: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating salary record"
        )


@router.get("/employee/{user_id}", response_model=EmployeeSalaryOut)
def get_salary_record(
    user_id: int,
    month: Optional[int] = Query(default=None, ge=1, le=12, description="Optional month (1-12) for month-specific in-hand"),
    year: Optional[int] = Query(default=None, ge=2000, le=2100, description="Optional year for month-specific in-hand"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get salary record for an employee.
    Employees can view their own salary, Admin/HR can view any.

    Optional query params:
    - month/year: when provided together, `monthly_in_hand` is calculated for that
      specific month (Professional Tax = 300 in Feb, 200 in other months).
    - when omitted, default `monthly_in_hand` remains annual-average based.
    """
    # Check permissions
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own salary information"
        )
    if current_user.role == RoleEnum.HR:
        target_user = get_user(db, user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )
        _enforce_hr_non_privileged_target(current_user, target_user, "view salary")
    
    # Fetch salary regardless of active status (include inactive too)
    salary = db.query(EmployeeSalary).filter(EmployeeSalary.user_id == user_id).first()
    if not salary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Salary record not found for this employee"
        )
    
    response = _salary_to_response(salary)

    # Month-specific monthly_professional_tax override.
    # (Professional Tax depends on month only; year is not required for this.)
    if month is not None:
        pt_monthly = 0.0 if (salary.professional_tax_annual or 0) <= 0 else (300.0 if month == 2 else 200.0)
        response["monthly_professional_tax"] = round(pt_monthly, 2)

    # Month-specific monthly_in_hand override (requires both month and year).
    if month is not None or year is not None:
        if month is None or year is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide both month and year together for month-specific monthly_in_hand."
            )

        monthly_gross = round(salary.total_earnings_annual / 12, 2)
        pt_monthly = 0.0 if (salary.professional_tax_annual or 0) <= 0 else (300.0 if month == 2 else 200.0)
        other_ded_monthly = round((salary.other_deduction_annual or 0) / 12, 2)
        pf_monthly = round((salary.pf_annual or 0) / 12, 2)
        response["monthly_in_hand"] = round(
            monthly_gross - pt_monthly - other_ded_monthly - pf_monthly,
            2
        )
        response["monthly_professional_tax"] = round(pt_monthly, 2)

    return response


@router.put("/employee/{user_id}", response_model=EmployeeSalaryOut)
def update_salary_record(
    user_id: int,
    salary_update: EmployeeSalaryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Update salary record (only non-calculated fields like bank details, variable pay).
    Use /employee/{user_id}/update-ctc to change CTC and recalculate components.
    """
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    _enforce_hr_non_privileged_target(current_user, user, "update salary")

    salary = update_employee_salary(db, user_id, salary_update)
    if not salary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Salary record not found for this employee"
        )
    
    return _salary_to_response(salary)


@router.put("/employee/{user_id}/manual-full-edit", response_model=EmployeeSalaryOut)
def update_salary_record_manual_full(
    user_id: int,
    salary_update: EmployeeSalaryManualFullUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Manual full-edit update for salary components.
    Allows direct editing of component amounts (basic/hra/special/conveyance/medical/other etc.)
    without triggering automatic CTC-based recomputation.
    """
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    _enforce_hr_non_privileged_target(current_user, user, "update salary")

    try:
        salary = update_employee_salary_manual_full(db, user_id, salary_update)
        if not salary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salary record not found for this employee"
            )
        return _salary_to_response(salary)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/employee/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_salary_record(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN))
):
    """
    Delete salary record for an employee.
    Admin only.
    """
    if not delete_employee_salary(db, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Salary record not found for this employee"
        )
    return None


@router.put("/employee/{user_id}/status", response_model=EmployeeSalaryOut)
def update_salary_status(
    user_id: int,
    status_update: EmployeeSalaryStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
):
    """
    Activate/deactivate an employee salary record.
    Admin only.
    """
    salary = db.query(EmployeeSalary).filter(EmployeeSalary.user_id == user_id).first()
    if not salary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Salary record not found for this employee",
        )
    target_user = get_user(db, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    _enforce_hr_non_privileged_target(current_user, target_user, "update salary status")

    salary.is_active = status_update.is_active
    salary.updated_at = now_ist()
    db.commit()
    db.refresh(salary)

    return _salary_to_response(salary)


@router.get("/employees", response_model=List[EmployeeSalaryOut])
def list_salaries(
    department: Optional[str] = Query(
        None,
        description="Filter by department. Supports comma-separated values (e.g. 'Sales,HR').",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    List all employee salaries.
    Admin/HR only.
    """
    departments: Optional[List[str]] = None
    if department:
        tokens_lower = department_tokens_lower(department)
        if not tokens_lower:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one non-empty department value must be provided when using the department filter",
            )

        # Validate against active departments master data
        rows = (
            db.query(Department.name)
            .filter(func.lower(Department.name).in_(tokens_lower))
            .filter(Department.status == "active")
            .all()
        )
        found_lower = {name.lower() for (name,) in rows if name}
        missing = [tok for tok in tokens_lower if tok not in found_lower]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid department(s): {missing}",
            )

        # Use canonical department names from master data for filtering
        departments = [name for (name,) in rows]

    salaries = list_employee_salaries(db, departments, skip, limit)
    if current_user.role == RoleEnum.HR and salaries:
        user_ids = [s.user_id for s in salaries]
        disallowed_ids = {
            uid for (uid,) in db.query(User.user_id)
            .filter(User.user_id.in_(user_ids), User.role.in_([RoleEnum.ADMIN, RoleEnum.HR]))
            .all()
        }
        salaries = [s for s in salaries if s.user_id not in disallowed_ids]
    return [_salary_to_response(s) for s in salaries]


# ==================== SALARY INCREMENT ENDPOINTS ====================

@router.post("/increment", response_model=SalaryIncrementOut, status_code=status.HTTP_201_CREATED)
def create_increment(
    increment_data: SalaryIncrementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Create salary increment record with automatic CTC calculation and update.
    
    Provide either:
    - increment_ctc_annual: Annual CTC increment amount (e.g., 50000 for ₹50,000/year)
    - increment_percentage: Increment percentage (e.g., 10 for 10%)
    
    The system will:
    1. Calculate the new CTC based on the employee's current CTC
    2. Update the employee's salary record (recalculates all components)
    3. Create an increment record with CTC details
    4. Send a notification to the employee
    
    Admin/HR only.
    """
    # Verify user exists
    user = get_user(db, increment_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {increment_data.user_id} not found"
        )
    _enforce_hr_non_privileged_target(current_user, user, "create increment")
    
    try:
        increment = create_salary_increment(db, increment_data, current_user.user_id)
        
        # Create notification for the employee with CTC details
        create_salary_notification(
            db=db,
            user_id=increment_data.user_id,
            notification_type="increment",
            title="Salary Increment Approved",
            message=f"Congratulations! Your salary increment of ₹{increment.increment_ctc_annual:,.2f} "
                    f"({increment.increment_percentage}%) has been approved. "
                    f"New CTC: ₹{increment.new_ctc_annual:,.2f}"
        )
        
        return _increment_to_out(increment, db)
    except ValueError as e:
        # Handle validation errors (e.g., no salary record found)
        logger.error(f"Validation error creating increment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating increment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating increment record"
        )


@router.get("/increment/{increment_id}", response_model=SalaryIncrementOut)
def get_increment(
    increment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get increment record by ID.
    """
    increment = get_salary_increment(db, increment_id)
    if not increment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Increment record not found"
        )
    
    # Check permissions
    if current_user.user_id != increment.user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own increment records"
        )
    if current_user.role == RoleEnum.HR:
        target_user = get_user(db, increment.user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {increment.user_id} not found"
            )
        _enforce_hr_non_privileged_target(current_user, target_user, "view increment")
    
    return _increment_to_out(increment, db)


@router.get("/increments/{user_id}", response_model=List[SalaryIncrementOut])
def get_user_increment_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all increment records for a user.
    """
    # Check permissions
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own increment history"
        )
    if current_user.role == RoleEnum.HR:
        target_user = get_user(db, user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )
        _enforce_hr_non_privileged_target(current_user, target_user, "view increment history")
    
    increments = get_user_increments(db, user_id)
    return [_increment_to_out(inc, db) for inc in increments]


# ==================== PDF GENERATION ENDPOINTS ====================


def _parse_slip_optional_custom_deductions(
    label_1: Optional[str],
    amount_1: Optional[float],
    label_2: Optional[str],
    amount_2: Optional[float],
    label_3: Optional[str],
    amount_3: Optional[float],
) -> Tuple[List[Tuple[str, float]], float]:
    """
    Up to three optional manual deductions for the slip (label + monthly amount).
    If amount > 0, a non-empty label is required for that slot.
    Label with no positive amount is ignored.
    """
    slots = [(label_1, amount_1), (label_2, amount_2), (label_3, amount_3)]
    out: List[Tuple[str, float]] = []
    total = 0.0
    for idx, (lab, amt) in enumerate(slots, start=1):
        lab_s = (lab or "").strip() if lab is not None else ""
        if amt is not None and float(amt) > 0 and not lab_s:
            raise ValueError(
                f"optional_deduction_{idx}_label is required when optional_deduction_{idx}_amount is provided."
            )
        if not lab_s or amt is None:
            continue
        a = round(float(amt), 2)
        if a <= 0:
            continue
        out.append((lab_s, a))
        total += a
    return out, total


@router.get("/slip/download/{user_id}")
def download_salary_slip(
    user_id: int,
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2000, le=2100, description="Year"),
    optional_deduction_1_label: Optional[str] = Query(None, description="Optional deduction 1 label (e.g. Insurance)"),
    optional_deduction_1_amount: Optional[float] = Query(None, ge=0, description="Optional deduction 1 amount (monthly)"),
    optional_deduction_2_label: Optional[str] = Query(None, description="Optional deduction 2 label"),
    optional_deduction_2_amount: Optional[float] = Query(None, ge=0, description="Optional deduction 2 amount (monthly)"),
    optional_deduction_3_label: Optional[str] = Query(None, description="Optional deduction 3 label"),
    optional_deduction_3_amount: Optional[float] = Query(None, ge=0, description="Optional deduction 3 amount (monthly)"),
    # pf_no: Optional[str] = Query(None, description="PF Number"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download salary slip PDF for an employee.
    Employees can download their own, Admin/HR can download any.
    
    The salary slip uses the current salary-structure logic:
    - Monthly Gross = total_earnings_annual / 12
    - Deductions = Professional Tax (₹200/month, Feb ₹300) + Other Tax (other_deduction_annual/12) + PF (pf_annual/12)
      + up to 3 optional manual deductions (optional_deduction_N_label + optional_deduction_N_amount)
    - Net Payable = (Monthly Gross + Variable Pay Monthly) - Deductions
    """
    # Check permissions
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only download your own salary slip"
        )
    
    try:
        # Get user and salary info
        user = get_user(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )

        # HR restriction: HR can only download PDFs for non-Admin and non-HR users.
        # HR is allowed to download their own (target == current_user) slip.
        _enforce_hr_non_privileged_target(current_user, user, "view salary slip")
        
        salary = get_employee_salary(db, user_id)
        if not salary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salary record not found for this employee"
            )
        
        custom_deductions, custom_deductions_total = _parse_slip_optional_custom_deductions(
            optional_deduction_1_label,
            optional_deduction_1_amount,
            optional_deduction_2_label,
            optional_deduction_2_amount,
            optional_deduction_3_label,
            optional_deduction_3_amount,
        )

        # Generate PDF (PF No is taken from salary record)
        pdf_buffer = _generate_salary_slip(
            user, salary, month, year, custom_deductions=custom_deductions
        )
        
        # Record in history using slip calculation values
        gross = salary.total_earnings_annual / 12
        variable_pay_monthly = round(salary.variable_pay / 12, 2) if salary.variable_pay else 0.0
        
        # Employee deductions = Professional Tax (month-specific) + Other Tax + PF + optional manual
        pt_monthly = 0.0 if (salary.professional_tax_annual or 0) <= 0 else (300.0 if month == 2 else 200.0)
        pf_monthly = round((salary.pf_annual or 0) / 12, 2)
        employee_deductions = (
            pt_monthly + (salary.other_deduction_annual / 12) + pf_monthly + custom_deductions_total
        )
        
        # Net = Gross + variable pay - employee deductions
        net = (gross + variable_pay_monthly) - employee_deductions
        
        create_salary_slip_history(
            db, user_id, month, year, gross, employee_deductions, net, current_user.user_id
        )
        
        # Return PDF
        month_name = _get_month_name(month)
        filename = f"Salary_Slip_{month_name}_{year}_{user.name.replace(' ', '_')}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating salary slip: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating salary slip: {str(e)}"
        )


@router.post("/slip/send/{user_id}", response_model=EmailResponse)
def send_salary_slip(
    user_id: int,
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2000, le=2100, description="Year"),
    optional_deduction_1_label: Optional[str] = Query(None, description="Optional deduction 1 label"),
    optional_deduction_1_amount: Optional[float] = Query(None, ge=0, description="Optional deduction 1 amount (monthly)"),
    optional_deduction_2_label: Optional[str] = Query(None, description="Optional deduction 2 label"),
    optional_deduction_2_amount: Optional[float] = Query(None, ge=0, description="Optional deduction 2 amount (monthly)"),
    optional_deduction_3_label: Optional[str] = Query(None, description="Optional deduction 3 label"),
    optional_deduction_3_amount: Optional[float] = Query(None, ge=0, description="Optional deduction 3 amount (monthly)"),
    # pf_no: Optional[str] = Query(None, description="PF Number"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Generate and send salary slip via email.
    Admin/HR only. Requires employee email to be verified.

    Optional query params: optional_deduction_1/2/3 _label and _amount (monthly),
    same rules as GET slip/download.
    """
    try:
        # Get user and salary info
        user = get_user(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )

        # HR restriction: HR cannot send salary slips for Admin/HR targets,
        # including themselves (target == current_user).
        _enforce_hr_non_privileged_target(current_user, user, "send salary slip")
        
        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee does not have an email address"
            )
        
        # ✅ Enforce email verification before sending salary documents
        if not user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Employee email is not verified. Employee must login via OTP at least once before receiving salary documents."
            )
        
        salary = get_employee_salary(db, user_id)
        if not salary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salary record not found for this employee"
            )
        
        custom_deductions, custom_deductions_total = _parse_slip_optional_custom_deductions(
            optional_deduction_1_label,
            optional_deduction_1_amount,
            optional_deduction_2_label,
            optional_deduction_2_amount,
            optional_deduction_3_label,
            optional_deduction_3_amount,
        )

        # Generate PDF (PF No is taken from salary record)
        pdf_buffer = _generate_salary_slip(
            user, salary, month, year, custom_deductions=custom_deductions
        )
        
        # Calculate net salary using slip logic (include variable pay when present)
        gross = salary.total_earnings_annual / 12
        variable_pay_monthly = round(salary.variable_pay / 12, 2) if salary.variable_pay else 0.0
        pt_monthly = 0.0 if (salary.professional_tax_annual or 0) <= 0 else (300.0 if month == 2 else 200.0)
        pf_monthly = round((salary.pf_annual or 0) / 12, 2)
        employee_deductions = (
            pt_monthly + (salary.other_deduction_annual / 12) + pf_monthly + custom_deductions_total
        )
        net_salary = (gross + variable_pay_monthly) - employee_deductions
        
        # Send email
        success = send_salary_slip_email(
            to_email=user.email,
            employee_name=user.name,
            month=month,
            year=year,
            pdf_buffer=pdf_buffer,
            net_salary=net_salary
        )
        
        if success:
            # Record in history using CTC-based calculation
            history = create_salary_slip_history(
                db, user_id, month, year, gross, employee_deductions, net_salary, current_user.user_id
            )
            update_slip_email_sent(db, history.id)
            
            # Create notification for the employee
            create_salary_notification(
                db=db,
                user_id=user_id,
                notification_type="salary_slip",
                title="Salary Slip Generated",
                message=f"Your salary slip for {_get_month_name(month)} {year} has been generated and sent to your email."
            )
            
            return EmailResponse(
                success=True,
                message=f"Salary slip sent successfully to {user.email}",
                email_sent_to=user.email
            )
        else:
            return EmailResponse(
                success=False,
                message="Failed to send salary slip email"
            )
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending salary slip: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending salary slip: {str(e)}"
        )


@router.get("/annexure/download/{user_id}")
def download_salary_annexure(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download salary annexure PDF for an employee.
    Employees can download their own, Admin/HR can download any.
    """
    # Check permissions
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only download your own salary annexure"
        )
    
    try:
        # Get user and salary info
        user = get_user(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )

        # HR restriction: HR can only download PDFs for non-Admin and non-HR users.
        # HR is allowed to download their own (target == current_user) annexure.
        _enforce_hr_non_privileged_target(current_user, user, "view salary annexure")
        
        salary = get_employee_salary(db, user_id)
        if not salary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salary record not found for this employee"
            )
        
        # Generate PDF with employer PF for correct CTC display
        pdf_buffer = generate_salary_annexure_pdf(
            employee_name=user.name,
            designation=user.designation or "Employee",
            location=user.address or "Office",
            basic_annual=salary.basic_annual,
            hra_annual=salary.hra_annual,
            special_allowance_annual=salary.special_allowance_annual,
            conveyance_annual=salary.conveyance_annual,
            medical_allowance_annual=salary.medical_allowance_annual,
            other_allowance_annual=salary.other_allowance_annual,
            professional_tax_annual=salary.professional_tax_annual,
            other_deduction_annual=salary.other_deduction_annual,
            employer_pf_annual=salary.pf_annual,
            variable_pay_annual=salary.variable_pay
        )
        
        filename = f"Salary_Annexure_{user.name.replace(' ', '_')}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating salary annexure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating salary annexure: {str(e)}"
        )


@router.post("/annexure/send/{user_id}", response_model=EmailResponse)
def send_salary_annexure(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Generate and send salary annexure via email.
    Admin/HR only. Requires employee email to be verified.
    """
    try:
        user = get_user(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )

        # HR restriction: HR cannot send salary annexures for Admin/HR targets,
        # including themselves (target == current_user).
        _enforce_hr_non_privileged_target(current_user, user, "send salary annexure")
        
        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee does not have an email address"
            )
        
        # ✅ Enforce email verification before sending salary documents
        if not user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Employee email is not verified. Employee must login via OTP at least once before receiving salary documents."
            )
        
        salary = get_employee_salary(db, user_id)
        if not salary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salary record not found for this employee"
            )
        
        # Generate PDF with employer PF for correct CTC display
        pdf_buffer = generate_salary_annexure_pdf(
            employee_name=user.name,
            designation=user.designation or "Employee",
            location=user.address or "Office",
            basic_annual=salary.basic_annual,
            hra_annual=salary.hra_annual,
            special_allowance_annual=salary.special_allowance_annual,
            conveyance_annual=salary.conveyance_annual,
            medical_allowance_annual=salary.medical_allowance_annual,
            other_allowance_annual=salary.other_allowance_annual,
            professional_tax_annual=salary.professional_tax_annual,
            other_deduction_annual=salary.other_deduction_annual,
            employer_pf_annual=salary.pf_annual,
            variable_pay_annual=salary.variable_pay
        )
        
        # Send email
        success = send_salary_annexure_email(
            to_email=user.email,
            employee_name=user.name,
            designation=user.designation or "Employee",
            ctc_annual=salary.ctc_annual,
            pdf_buffer=pdf_buffer
        )
        
        if success:
            # Create notification for the employee
            create_salary_notification(
                db=db,
                user_id=user_id,
                notification_type="annexure",
                title="Salary Annexure Sent",
                message="Your salary annexure has been generated and sent to your email."
            )
            
            return EmailResponse(
                success=True,
                message=f"Salary annexure sent successfully to {user.email}",
                email_sent_to=user.email
            )
        else:
            return EmailResponse(
                success=False,
                message="Failed to send salary annexure email"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending salary annexure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending salary annexure: {str(e)}"
        )


# ==================== INCREMENT LETTER ENDPOINTS ====================

@router.get("/increment-letter/download/{increment_id}")
def download_increment_letter(
    increment_id: int,
    title: Optional[Literal['Mr', 'Mrs', 'Miss']] = Query(None, description="Optional title to use before the employee name (Mr, Mrs, Miss)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download increment letter PDF.
    Employees can download their own, Admin/HR can download any.
    """
    try:
        increment = get_salary_increment(db, increment_id)
        if not increment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Increment record not found"
            )
        
        # Check permissions
        if current_user.user_id != increment.user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only download your own increment letter"
            )
        
        user = get_user(db, increment.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )

        # HR restriction: HR can only download PDFs for non-Admin and non-HR users.
        # HR is allowed to download their own (target == current_user) increment letter.
        _enforce_hr_non_privileged_target(current_user, user, "view increment letter")
        
        # Fetch employee salary record for annexure details
        salary = get_employee_salary(db, increment.user_id)
        
        # Generate PDF with salary annexure if salary record exists
        if salary:
            pdf_buffer = generate_increment_letter_pdf(
                employee_name=user.name,
                designation=user.designation or "Employee",
                location=user.address or "Office",
                previous_salary=increment.previous_salary,
                increment_amount=increment.increment_amount,
                new_salary=increment.new_salary,
                effective_date=increment.effective_date,
                title=title,
                include_salary_annexure=True,
                basic_annual=salary.basic_annual,
                hra_annual=salary.hra_annual,
                special_allowance_annual=salary.special_allowance_annual,
                conveyance_annual=salary.conveyance_annual,
                medical_allowance_annual=salary.medical_allowance_annual,
                other_allowance_annual=salary.other_allowance_annual,
                professional_tax_annual=salary.professional_tax_annual,
                other_deduction_annual=salary.other_deduction_annual,
                employer_pf_annual=salary.pf_annual,
                variable_pay_annual=salary.variable_pay
            )
        else:
            # Generate without annexure if salary record doesn't exist
            pdf_buffer = generate_increment_letter_pdf(
                employee_name=user.name,
                designation=user.designation or "Employee",
                location=user.address or "Office",
                previous_salary=increment.previous_salary,
                increment_amount=increment.increment_amount,
                new_salary=increment.new_salary,
                effective_date=increment.effective_date,
                title=title,
                include_salary_annexure=False
            )
        
        filename = f"Increment_Letter_{user.name.replace(' ', '_')}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating increment letter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating increment letter: {str(e)}"
        )


@router.post("/increment-letter/send/{increment_id}", response_model=EmailResponse)
def send_increment_letter(
    increment_id: int,
    title: Optional[Literal['Mr', 'Mrs', 'Miss']] = Query(None, description="Optional title to use before the employee name (Mr, Mrs, Miss)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Generate and send increment letter via email.
    Admin/HR only. Requires employee email to be verified.
    """
    try:
        increment = get_salary_increment(db, increment_id)
        if not increment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Increment record not found"
            )
        
        user = get_user(db, increment.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        _enforce_hr_non_privileged_target(current_user, user, "send increment letter")
        
        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee does not have an email address"
            )
        
        # ✅ Enforce email verification before sending salary documents
        if not user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Employee email is not verified. Employee must login via OTP at least once before receiving salary documents."
            )
        
        # Fetch employee salary record for annexure details
        salary = get_employee_salary(db, increment.user_id)
        
        # Generate PDF with salary annexure if salary record exists
        if salary:
            pdf_buffer = generate_increment_letter_pdf(
                employee_name=user.name,
                designation=user.designation or "Employee",
                location=user.address or "Office",
                previous_salary=increment.previous_salary,
                increment_amount=increment.increment_amount,
                new_salary=increment.new_salary,
                effective_date=increment.effective_date,
                title=title,
                include_salary_annexure=True,
                basic_annual=salary.basic_annual,
                hra_annual=salary.hra_annual,
                special_allowance_annual=salary.special_allowance_annual,
                conveyance_annual=salary.conveyance_annual,
                medical_allowance_annual=salary.medical_allowance_annual,
                other_allowance_annual=salary.other_allowance_annual,
                professional_tax_annual=salary.professional_tax_annual,
                other_deduction_annual=salary.other_deduction_annual,
                employer_pf_annual=salary.pf_annual,
                variable_pay_annual=salary.variable_pay
            )
        else:
            # Generate without annexure if salary record doesn't exist
            pdf_buffer = generate_increment_letter_pdf(
                employee_name=user.name,
                designation=user.designation or "Employee",
                location=user.address or "Office",
                previous_salary=increment.previous_salary,
                increment_amount=increment.increment_amount,
                new_salary=increment.new_salary,
                effective_date=increment.effective_date,
                title=title,
                include_salary_annexure=False
            )
        
        # Send email
        success = send_increment_letter_email(
            to_email=user.email,
            employee_name=user.name,
            previous_salary=increment.previous_salary,
            new_salary=increment.new_salary,
            increment_amount=increment.increment_amount,
            effective_date=increment.effective_date,
            pdf_buffer=pdf_buffer
        )
        
        if success:
            update_increment_letter_sent(db, increment_id)
            
            # Create notification for the employee
            create_salary_notification(
                db=db,
                user_id=increment.user_id,
                notification_type="increment",
                title="Increment Letter Sent",
                message=f"Your increment letter has been generated and sent to your email. New salary: ₹{increment.new_salary:,.2f}"
            )
            
            return EmailResponse(
                success=True,
                message=f"Increment letter sent successfully to {user.email}",
                email_sent_to=user.email
            )
        else:
            return EmailResponse(
                success=False,
                message="Failed to send increment letter email"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending increment letter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending increment letter: {str(e)}"
        )


# ==================== OFFER LETTER ENDPOINT ====================

@router.get("/offer-letter/download/{user_id}")
def download_offer_letter(
    user_id: int,
    letter_date: str = Query(..., description="Letter creation date (YYYY-MM-DD)."),
    joining_date: str = Query(..., description="Joining date (YYYY-MM-DD). Must be same or later than letter_date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Download offer letter with salary annexure PDF.
    Admin/HR only.
    """
    try:
        user = get_user(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )

        # HR restriction:
        # HR cannot download offer letters for Admins, other HRs, or even themselves.
        _enforce_hr_non_privileged_target(current_user, user, "download offer letter")
        
        salary = get_employee_salary(db, user_id)
        if not salary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salary record not found for this employee"
            )
        
        # Parse and validate letter_date (required)
        try:
            parsed_letter = datetime.strptime(letter_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid letter_date format. Use YYYY-MM-DD")
        # joining_date is required; parse and validate it against parsed_letter
        try:
            parsed_joining = datetime.strptime(joining_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid joining_date format. Use YYYY-MM-DD")
        if parsed_joining.date() < parsed_letter.date():
            raise HTTPException(status_code=400, detail="joining_date cannot be earlier than the letter date")
        resolved_joining_date = parsed_joining

        # Generate PDF with employer PF for correct CTC display
        pdf_buffer = generate_offer_letter_pdf(
            employee_name=user.name,
            designation=user.designation or "Employee",
            location=user.address or "Office",
            joining_date=resolved_joining_date,
            basic_annual=salary.basic_annual,
            hra_annual=salary.hra_annual,
            special_allowance_annual=salary.special_allowance_annual,
            conveyance_annual=salary.conveyance_annual,
            medical_allowance_annual=salary.medical_allowance_annual,
            other_allowance_annual=salary.other_allowance_annual,
            professional_tax_annual=salary.professional_tax_annual,
            other_deduction_annual=salary.other_deduction_annual,
            employer_pf_annual=salary.pf_annual,
            variable_pay_annual=salary.variable_pay,
            letter_date=parsed_letter
        )
        
        filename = f"Offer_Letter_{user.name.replace(' ', '_')}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating offer letter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating offer letter: {str(e)}"
        )


# ==================== SALARY SLIP HISTORY ====================

@router.get("/slip/history/{user_id}")
def get_slip_history(
    user_id: int,
    year: Optional[int] = Query(None, description="Filter by year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get salary slip generation history for an employee.
    """
    # Check permissions
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own salary slip history"
        )

    # HR restriction: HR cannot view Admin/other-HR details.
    # HR can view their own history (handled inside the helper).
    target_user = get_user(db, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    _enforce_hr_non_privileged_target(current_user, target_user, "view salary slip history")
    
    history = get_user_salary_slip_history(db, user_id, year)
    return {"history": history}


# ==================== SALARY NOTIFICATION ENDPOINTS ====================

@router.get("/notifications", response_model=List[SalaryNotificationOut])
def get_my_salary_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all salary notifications for the current user.
    Employees can view their own notifications.
    """
    notifications = list_salary_notifications(db, current_user.user_id)
    return notifications


@router.get("/notifications/{user_id}", response_model=List[SalaryNotificationOut])
def get_user_salary_notifications(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all salary notifications for a specific user.
    Employees can view their own, Admin/HR can view any.
    """
    # Check permissions
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own notifications"
        )
    
    notifications = list_salary_notifications(db, user_id)
    return notifications


@router.put("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark a salary notification as read.
    Users can only mark their own notifications as read.
    """
    notification = mark_salary_notification_as_read(db, notification_id, current_user.user_id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or does not belong to you"
        )
    
    return {"success": True, "message": "Notification marked as read"}


@router.get("/notifications/unread/count")
def get_unread_notifications_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get count of unread salary notifications for the current user.
    """
    count = get_unread_salary_notifications_count(db, current_user.user_id)
    return {"unread_count": count}


# ==================== HELPER FUNCTIONS ====================

def _salary_to_response(salary: EmployeeSalary) -> dict:
    """Convert salary model to response dict with computed fields"""
    # Some legacy/manual salary records may not have package_ctc_annual stored.
    # EmployeeSalaryOut requires a float, so fall back to calculated CTC.
    package_ctc_annual = (
        salary.package_ctc_annual
        if getattr(salary, "package_ctc_annual", None) is not None
        else salary.ctc_annual
    )

    monthly_gross = round(salary.total_earnings_annual / 12, 2)
    other_ded_monthly = round((salary.other_deduction_annual or 0) / 12, 2)
    pf_monthly = round((salary.pf_annual or 0) / 12, 2)

    # Professional Tax rules: Feb = 300, other months = 200 (if PT is enabled on the salary record).
    if (salary.professional_tax_annual or 0) <= 0:
        feb_monthly_prof_tax = 0.0
        other_monthly_prof_tax = 0.0
    else:
        feb_monthly_prof_tax = 300.0
        other_monthly_prof_tax = 200.0

    feb_monthly_in_hand = round(
        monthly_gross - feb_monthly_prof_tax - other_ded_monthly - pf_monthly,
        2,
    )
    other_monthly_in_hand = round(
        monthly_gross - other_monthly_prof_tax - other_ded_monthly - pf_monthly,
        2,
    )
    return {
        "id": salary.id,
        "user_id": salary.user_id,
        "basic_annual": salary.basic_annual,
        "hra_annual": salary.hra_annual,
        "special_allowance_annual": salary.special_allowance_annual,
        "conveyance_annual": salary.conveyance_annual,
        "medical_allowance_annual": salary.medical_allowance_annual,
        "other_allowance_annual": salary.other_allowance_annual,
        "professional_tax_annual": salary.professional_tax_annual,
        "other_deduction_annual": salary.other_deduction_annual,
        "pf_annual": salary.pf_annual,
        "pan_number": salary.pan_number,
        "uan_number": salary.uan_number,
        "pf_no": salary.pf_no,
        "bank_name": salary.bank_name,
        "bank_account": salary.bank_account,
        "ifsc_code": salary.ifsc_code,
        "variable_pay": salary.variable_pay,
        "working_days_per_month": salary.working_days_per_month,
        "payment_mode": salary.payment_mode,
        "is_active": salary.is_active,
        "created_at": salary.created_at,
        "updated_at": salary.updated_at,
        "total_earnings_annual": salary.total_earnings_annual,
        "total_deductions_annual": salary.total_deductions_annual,
        "package_ctc_annual": float(package_ctc_annual),  # Offered package CTC (or computed fallback)
        "display_ctc_annual": salary.display_ctc_annual,  # CTC to display (package if set, else calculated)
        "monthly_ctc": salary.monthly_ctc,  # Calculated monthly CTC
        "display_monthly_ctc": salary.display_monthly_ctc,  # Monthly CTC to display
        "monthly_in_hand": salary.monthly_in_hand,
        # Default monthly professional tax is annual-average; will be
        # overridden when month/year are provided.
        "monthly_professional_tax": round((salary.professional_tax_annual or 0.0) / 12, 2),
        "feb_monthly_in_hand": feb_monthly_in_hand,
        "other_monthly_in_hand": other_monthly_in_hand,
        "feb_monthly_prof_tax": round(feb_monthly_prof_tax, 2),
        "other_monthly_prof_tax": round(other_monthly_prof_tax, 2),
    }


def _generate_salary_slip(
    user: User,
    salary: EmployeeSalary,
    month: int,
    year: int,
    pf_no: Optional[str] = None,
    custom_deductions: Optional[List[Tuple[str, float]]] = None,
):
    """
    Generate salary slip PDF for user using CTC-based calculation logic.
    
    The salary record contains components calculated from CTC:
    - Total Gross = CTC - (Employer PF)
    - Basic = 50% of Total Gross
    - HRA = 50% of Basic
    - Medical Allowance = ₹13,200/year (fixed)
    - Conveyance Allowance = ₹15,000/year (fixed)
    - Other Allowance = ₹3,000/year (fixed)
    - Special Allowance = Remaining balance
    
    Deductions:
    - Professional Tax = ₹200/month (Feb ₹300) (₹2,500/year)
    - Other Tax = ₹1,000/month (₹12,000/year) - stored in other_deduction_annual
    - Employer PF = 12% of Basic - stored in pf_annual (treated as employee deduction for net calculation)
    """
    # Calculate monthly values from annual values
    basic_monthly = round(salary.basic_annual / 12, 2)
    hra_monthly = round(salary.hra_annual / 12, 2)
    special_monthly = round(salary.special_allowance_annual / 12, 2)
    medical_monthly = round(salary.medical_allowance_annual / 12, 2)
    conveyance_monthly = round(salary.conveyance_annual / 12, 2)
    other_monthly = round(salary.other_allowance_annual / 12, 2)
    
    # Deductions (monthly)
    pt_monthly = 0.0 if (salary.professional_tax_annual or 0) <= 0 else (300.0 if month == 2 else 200.0)
    other_ded_monthly = round(salary.other_deduction_annual / 12, 2)  # ₹1,000/month (Other Tax)
    
    # Employer PF (shown in slip and also treated as an employee deduction for net calculation)
    employer_pf_monthly = round(salary.pf_annual / 12, 2) if salary.pf_annual else 0
    
    # Variable pay (monthly)
    variable_pay_monthly = round(salary.variable_pay / 12, 2) if salary.variable_pay else 0
    
    # Format joining date
    doj = user.joining_date.strftime("%d-%m-%Y") if user.joining_date else "N/A"
    
    # Format PF display - show employer PF contribution
    pf_display = "NA"
    if employer_pf_monthly > 0:
        pf_display = f"{employer_pf_monthly:,.2f}"

    return generate_salary_slip_pdf(
        employee_name=user.name,
        employee_id=user.employee_id or str(user.user_id),
        designation=user.designation or "Employee",
        location="Pune",
        doj=doj,
        pan=salary.pan_number or user.pan_card or "N/A",
        uan=salary.uan_number or "NA",
        month=month,
        year=year,
        working_days=salary.working_days_per_month,
        pf=pf_display,
        variable_pay=variable_pay_monthly,
        basic=basic_monthly,
        hra=hra_monthly,
        special_allowance=special_monthly,
        medical_allowance=medical_monthly,
        conveyance=conveyance_monthly,
        other_allowance=other_monthly,
        professional_tax=pt_monthly,
        other_deduction=other_ded_monthly,
        pf_no=(pf_no or getattr(salary, "pf_no", None) or ""),
        payment_mode=salary.payment_mode,
        bank_name=salary.bank_name or "",
        bank_account=salary.bank_account or "",
        custom_deductions=custom_deductions,
    )


def _get_month_name(month: int) -> str:
    """Get month name from number"""
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    return months[month - 1] if 1 <= month <= 12 else ""
