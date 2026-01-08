"""
Salary Routes - API endpoints for salary slip, increment letter, and salary annexure
Admin/HR only access with role-based permissions
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import logging
import traceback

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.salary import EmployeeSalary, SalaryIncrement
from app.dependencies import get_current_user, require_roles
from app.enums import RoleEnum
from app.schemas.salary_schema import (
    EmployeeSalaryCreate, EmployeeSalaryUpdate, EmployeeSalaryOut,
    EmployeeSalaryCTCCreate, EmployeeSalaryCTCUpdate, SalaryCalculationPreview,
    SalaryIncrementCreate, SalaryIncrementOut,
    SalarySlipRequest, IncrementLetterRequest, SalaryAnnexureRequest,
    EmailResponse, VariablePayType
)
from app.crud.salary_crud import (
    create_employee_salary, create_employee_salary_from_ctc, get_employee_salary, 
    update_employee_salary, update_employee_salary_from_ctc, delete_employee_salary, 
    list_employee_salaries, preview_salary_calculation,
    create_salary_increment, get_salary_increment, get_user_increments,
    get_latest_increment, update_increment_letter_sent,
    create_salary_slip_history, get_salary_slip_history, update_slip_email_sent,
    get_user_salary_slip_history
)
from app.services.salary_pdf_services import (
    generate_salary_slip_pdf, generate_salary_annexure_pdf,
    generate_increment_letter_pdf, generate_offer_letter_pdf
)
from app.services.salary_email_service import (
    send_salary_slip_email, send_increment_letter_email, send_salary_annexure_email
)
from app.services.salary_calculation_service import SalaryCalculator
from app.crud.user_crud import get_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/salary", tags=["Salary Management"])


# ==================== CTC-BASED PAYROLL ENDPOINTS ====================

@router.post("/calculate-preview", response_model=SalaryCalculationPreview)
def preview_ctc_calculation(
    annual_ctc: float = Query(..., gt=0, description="Annual CTC amount"),
    variable_pay_type: VariablePayType = Query(default=VariablePayType.NONE),
    variable_pay_value: float = Query(default=0.0, ge=0),
    employer_pf_percentage: float = Query(default=12.0, ge=0, le=100, description="Employer PF percentage"),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Preview salary calculation from CTC without saving.
    Shows breakdown of all components for HR review.
    """
    try:
        return preview_salary_calculation(
            annual_ctc=annual_ctc,
            variable_pay_type=variable_pay_type.value,
            variable_pay_value=variable_pay_value,
            employer_pf_percentage=employer_pf_percentage
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/minimum-ctc")
def get_minimum_ctc(
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """Get minimum CTC required for fixed components"""
    min_ctc = SalaryCalculator.get_minimum_ctc()
    return {
        "minimum_ctc": min_ctc,
        "formatted": f"₹{min_ctc:,.2f}",
        "components": {
            "medical_annual": SalaryCalculator.MEDICAL_ALLOWANCE_ANNUAL,
            "conveyance_annual": SalaryCalculator.CONVEYANCE_ALLOWANCE_ANNUAL,
            "other_annual": SalaryCalculator.OTHER_ALLOWANCE_ANNUAL,
            "basic_percentage": f"{SalaryCalculator.BASIC_PERCENTAGE * 100}%",
            "hra_percentage": f"{SalaryCalculator.HRA_PERCENTAGE * 100}% of Basic"
        }
    }


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
    
    try:
        salary = create_employee_salary_from_ctc(db, salary_data)
        return _salary_to_response(salary)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get salary record for an employee.
    Employees can view their own salary, Admin/HR can view any.
    """
    # Check permissions
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own salary information"
        )
    
    salary = get_employee_salary(db, user_id)
    if not salary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Salary record not found for this employee"
        )
    
    return _salary_to_response(salary)


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
    salary = update_employee_salary(db, user_id, salary_update)
    if not salary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Salary record not found for this employee"
        )
    
    return _salary_to_response(salary)


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


@router.get("/employees", response_model=List[EmployeeSalaryOut])
def list_salaries(
    department: Optional[str] = Query(None, description="Filter by department"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    List all employee salaries.
    Admin/HR only.
    """
    salaries = list_employee_salaries(db, department, skip, limit)
    return [_salary_to_response(s) for s in salaries]


# ==================== SALARY INCREMENT ENDPOINTS ====================

@router.post("/increment", response_model=SalaryIncrementOut, status_code=status.HTTP_201_CREATED)
def create_increment(
    increment_data: SalaryIncrementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Create salary increment record.
    Admin/HR only.
    """
    # Verify user exists
    user = get_user(db, increment_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {increment_data.user_id} not found"
        )
    
    try:
        increment = create_salary_increment(db, increment_data, current_user.user_id)
        return increment
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
    
    return increment


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
    
    return get_user_increments(db, user_id)


# ==================== PDF GENERATION ENDPOINTS ====================

@router.get("/slip/download/{user_id}")
def download_salary_slip(
    user_id: int,
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2000, le=2100, description="Year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download salary slip PDF for an employee.
    Employees can download their own, Admin/HR can download any.
    
    The salary slip uses CTC-based calculation logic:
    - Total Gross = CTC - (Employer PF + Variable Pay)
    - Deductions: Professional Tax (₹200/month) + Other Tax (₹1,000/month)
    - Net Payable = Total Gross - Deductions
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
        
        salary = get_employee_salary(db, user_id)
        if not salary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salary record not found for this employee"
            )
        
        # Generate PDF
        pdf_buffer = _generate_salary_slip(user, salary, month, year)
        
        # Record in history using CTC-based calculation
        # Total Gross = sum of all earnings (already calculated from CTC)
        gross = salary.total_earnings_annual / 12
        
        # Employee deductions = Professional Tax + Other Tax (not Employer PF)
        # Employer PF is stored in pf_annual but is NOT deducted from employee salary
        employee_deductions = (salary.professional_tax_annual + salary.other_deduction_annual) / 12
        
        # Net = Gross - Employee Deductions
        net = gross - employee_deductions
        
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """
    Generate and send salary slip via email.
    Admin/HR only. Requires employee email to be verified.
    
    Uses CTC-based calculation logic for salary components.
    """
    try:
        # Get user and salary info
        user = get_user(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
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
        
        # Generate PDF
        pdf_buffer = _generate_salary_slip(user, salary, month, year)
        
        # Calculate net salary using CTC-based logic
        # Net = Total Gross - Employee Deductions (Professional Tax + Other Tax)
        # Employer PF is NOT deducted from employee salary
        gross = salary.total_earnings_annual / 12
        employee_deductions = (salary.professional_tax_annual + salary.other_deduction_annual) / 12
        net_salary = gross - employee_deductions
        
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
        
        salary = get_employee_salary(db, user_id)
        if not salary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salary record not found for this employee"
            )
        
        # Generate PDF with employer PF for correct CTC display
        pdf_buffer = generate_offer_letter_pdf(
            employee_name=user.name,
            designation=user.designation or "Employee",
            location=user.address or "Office",
            joining_date=user.joining_date or datetime.now(),
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
    
    history = get_user_salary_slip_history(db, user_id, year)
    return {"history": history}


# ==================== HELPER FUNCTIONS ====================

def _salary_to_response(salary: EmployeeSalary) -> dict:
    """Convert salary model to response dict with computed fields"""
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
        "ctc_annual": salary.ctc_annual,
        "monthly_ctc": salary.monthly_ctc,
        "monthly_in_hand": salary.monthly_in_hand
    }


def _generate_salary_slip(user: User, salary: EmployeeSalary, month: int, year: int):
    """
    Generate salary slip PDF for user using CTC-based calculation logic.
    
    The salary record contains components calculated from CTC:
    - Total Gross = CTC - (Employer PF + Variable Pay)
    - Basic = 50% of Total Gross
    - HRA = 50% of Basic
    - Medical Allowance = ₹19,200/year (fixed)
    - Conveyance Allowance = ₹15,000/year (fixed)
    - Other Allowance = ₹3,000/year (fixed)
    - Special Allowance = Remaining balance
    
    Deductions:
    - Professional Tax = ₹200/month (₹2,400/year)
    - Other Tax = ₹1,000/month (₹12,000/year) - stored in other_deduction_annual
    - Employer PF = 12% of Basic - stored in pf_annual (not deducted from employee)
    """
    # Calculate monthly values from annual values
    basic_monthly = round(salary.basic_annual / 12, 2)
    hra_monthly = round(salary.hra_annual / 12, 2)
    special_monthly = round(salary.special_allowance_annual / 12, 2)
    medical_monthly = round(salary.medical_allowance_annual / 12, 2)
    conveyance_monthly = round(salary.conveyance_annual / 12, 2)
    other_monthly = round(salary.other_allowance_annual / 12, 2)
    
    # Deductions (monthly)
    pt_monthly = round(salary.professional_tax_annual / 12, 2)  # ₹200/month
    other_ded_monthly = round(salary.other_deduction_annual / 12, 2)  # ₹1,000/month (Other Tax)
    
    # Employer PF (for display, not deducted from employee salary)
    employer_pf_monthly = round(salary.pf_annual / 12, 2) if salary.pf_annual else 0
    
    # Variable pay (monthly)
    variable_pay_monthly = round(salary.variable_pay / 12, 2) if salary.variable_pay else 0
    
    # Format joining date
    doj = user.joining_date.strftime("%d-%m-%Y") if user.joining_date else "N/A"
    
    # Format PF display - show employer PF contribution
    pf_display = "NA"
    if employer_pf_monthly > 0:
        pf_display = f"₹{employer_pf_monthly:,.2f}"
    
    return generate_salary_slip_pdf(
        employee_name=user.name,
        employee_id=user.employee_id or str(user.user_id),
        designation=user.designation or "Employee",
        location=user.address or "Office",
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
        payment_mode=salary.payment_mode
    )


def _get_month_name(month: int) -> str:
    """Get month name from number"""
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    return months[month - 1] if 1 <= month <= 12 else ""
