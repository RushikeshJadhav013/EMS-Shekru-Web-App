"""
Salary Calculation Service - Automatic salary component calculations based on CTC
"""
from typing import Dict, Optional
from enum import Enum


class VariablePayType(str, Enum):
    """Variable pay configuration options"""
    NONE = "none"
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class SalaryCalculator:
    """
    Automatic salary calculation based on Annual CTC
    
    Formula: Total Gross = CTC − (Employer PF + Variable Pay + Medical + Conveyance + Other + Professional Tax + Other Tax)
    
    Salary Components (derived from Total Gross):
    - Basic = 50% of Total Gross
    - HRA = 50% of Basic
    - Medical = ₹19,200/year (fixed)
    - Conveyance = ₹15,000/year (fixed)
    - Other = ₹3,000/year (fixed)
    - Special Allowance = Total Gross − (Basic + HRA + Medical + Conveyance + Other)
    
    Statutory Deductions (subtracted from CTC to get Total Gross):
    - Professional Tax = ₹200/month (₹2,400/year)
    - Other Tax = ₹1,000/month (₹12,000/year)
    
    Employer Contribution (subtracted from CTC to get Total Gross, NOT deducted from employee):
    - Employer PF = 12% of Basic (editable)
    
    Key Points:
    - Total Earnings (Annual) = Total Gross
    - Employer PF is NOT double-counted in deductions
    """
    
    # Fixed annual amounts
    MEDICAL_ALLOWANCE_ANNUAL = 19200.0
    CONVEYANCE_ALLOWANCE_ANNUAL = 15000.0
    OTHER_ALLOWANCE_ANNUAL = 3000.0
    PROFESSIONAL_TAX_ANNUAL = 2400.0  # ₹200/month
    OTHER_TAX_ANNUAL = 12000.0  # ₹1,000/month
    
    # Total fixed allowances (part of Total Gross)
    TOTAL_FIXED_ALLOWANCES = MEDICAL_ALLOWANCE_ANNUAL + CONVEYANCE_ALLOWANCE_ANNUAL + OTHER_ALLOWANCE_ANNUAL  # ₹37,200
    
    # Total fixed deductions (subtracted from CTC)
    TOTAL_FIXED_DEDUCTIONS = PROFESSIONAL_TAX_ANNUAL + OTHER_TAX_ANNUAL  # ₹14,400
    
    # Employer contributions
    EMPLOYER_PF_PERCENTAGE = 0.12  # 12% of Basic (editable)
    
    # Calculation percentages
    BASIC_PERCENTAGE = 0.50  # 50% of Total Gross
    HRA_PERCENTAGE = 0.50    # 50% of Basic
    
    @classmethod
    def calculate_salary_components(
        cls,
        annual_ctc: float,
        variable_pay_type: VariablePayType = VariablePayType.NONE,
        variable_pay_value: float = 0.0,
        employer_pf_percentage: float = None
    ) -> Dict[str, float]:
        """
        Calculate all salary components based on Annual CTC following strict payroll rules.
        
        NEW Formula: Total Gross = CTC − (Employer PF + Variable Pay + Medical + Conveyance + Other + Professional Tax + Other Tax)
        
        Steps:
        1. Calculate Variable Pay
        2. Calculate Total Gross using iterative approach:
           Total Gross = CTC − (Employer PF + Variable Pay + Medical ₹19,200 + Conveyance ₹15,000 + Other ₹3,000 + Professional Tax ₹2,400 + Other Tax ₹12,000)
           Since Employer PF = 12% of Basic and Basic = 50% of Total Gross:
           Employer PF = 12% × 50% × Total Gross = 6% × Total Gross
           So: Total Gross = CTC − (6% × Total Gross + Variable Pay + Fixed Deductions)
           Total Gross × (1 + 6%) = CTC − Variable Pay − Fixed Deductions
           Total Gross = (CTC − Variable Pay − Fixed Deductions) / (1 + 6%)
        3. Basic = 50% of Total Gross
        4. HRA = 50% of Basic
        5. Special Allowance = Total Gross − (Basic + HRA + Medical + Conveyance + Other)
        6. Employer PF = 12% of Basic (subtracted from CTC, NOT deducted from employee earnings)
        7. Total Earnings (Annual) = Total Gross (employee receives this)
        8. Monthly In-Hand = Total Gross / 12 (no additional deductions from earnings)
        
        Key Points:
        - Total Earnings = Total Gross
        - Employer PF is NOT double-counted in deductions (it's already subtracted from CTC)
        - Professional Tax and Other Tax are subtracted from CTC to calculate Total Gross
        
        Args:
            annual_ctc: Total annual CTC amount (Package)
            variable_pay_type: Type of variable pay (none/percentage/fixed)
            variable_pay_value: Value for variable pay (percentage or fixed amount)
            employer_pf_percentage: Employer PF percentage (default 12%, editable)
            
        Returns:
            Dictionary with all calculated salary components
        """
        if annual_ctc <= 0:
            raise ValueError("Annual CTC must be greater than 0")
        
        # Use default employer PF percentage if not provided
        if employer_pf_percentage is None:
            employer_pf_percentage = cls.EMPLOYER_PF_PERCENTAGE
        
        # Step 1: Calculate variable pay
        variable_pay_annual = cls._calculate_variable_pay(
            annual_ctc, variable_pay_type, variable_pay_value
        )
        
        # Fixed allowances (part of Total Gross earnings)
        medical_annual = cls.MEDICAL_ALLOWANCE_ANNUAL  # ₹19,200
        conveyance_annual = cls.CONVEYANCE_ALLOWANCE_ANNUAL  # ₹15,000
        other_annual = cls.OTHER_ALLOWANCE_ANNUAL  # ₹3,000
        fixed_allowances = medical_annual + conveyance_annual + other_annual  # ₹37,200
        
        # Fixed deductions (subtracted from CTC to get Total Gross)
        professional_tax_annual = cls.PROFESSIONAL_TAX_ANNUAL  # ₹2,400
        other_tax_annual = cls.OTHER_TAX_ANNUAL  # ₹12,000
        fixed_deductions = professional_tax_annual + other_tax_annual  # ₹14,400
        
        # Step 2: Calculate Total Gross
        # NEW Formula: Total Gross = CTC − (Employer PF + Variable Pay + Medical + Conveyance + Other + Professional Tax + Other Tax)
        # Where: Employer PF = PF% × Basic = PF% × 50% × Total Gross
        # So: Total Gross = CTC − (PF% × 50% × Total Gross) − Variable Pay − Fixed Allowances − Fixed Deductions
        # Total Gross + (PF% × 50% × Total Gross) = CTC − Variable Pay − Fixed Allowances − Fixed Deductions
        # Total Gross × (1 + PF% × 50%) = CTC − Variable Pay − Fixed Allowances − Fixed Deductions
        # Total Gross = (CTC − Variable Pay − Fixed Allowances − Fixed Deductions) / (1 + PF% × 50%)
        
        employer_pf_factor = employer_pf_percentage * cls.BASIC_PERCENTAGE  # 12% × 50% = 6%
        numerator = annual_ctc - variable_pay_annual - fixed_allowances - fixed_deductions
        total_gross = round(numerator / (1 + employer_pf_factor), 2)
        
        # Validate total gross is positive
        if total_gross <= 0:
            min_ctc = cls.get_minimum_ctc()
            raise ValueError(
                f"CTC amount ₹{annual_ctc:,.2f} is too low. "
                f"Minimum required CTC: ₹{min_ctc:,.2f}"
            )
        
        # Step 3: Basic = 50% of Total Gross
        basic_annual = round(total_gross * cls.BASIC_PERCENTAGE, 2)
        
        # Step 4: HRA = 50% of Basic
        hra_annual = round(basic_annual * cls.HRA_PERCENTAGE, 2)
        
        # Step 5: Special Allowance = Total Gross − (Basic + HRA)
        # Note: Fixed allowances are already subtracted from CTC, so Total Gross = Basic + HRA + Special
        special_allowance_annual = round(
            total_gross - basic_annual - hra_annual, 2
        )
        
        # Ensure special allowance is not negative
        if special_allowance_annual < 0:
            special_allowance_annual = 0.0
        
        # Step 6: Employer PF = 12% of Basic (already subtracted from CTC, NOT deducted from employee)
        employer_pf_annual = round(basic_annual * employer_pf_percentage, 2)
        
        # Step 7: Total Earnings = Total Gross = Basic + HRA + Special Allowance
        # Note: Fixed allowances (Medical, Conveyance, Other) are shown separately but are part of CTC breakdown
        total_earnings_annual = total_gross  # = Basic + HRA + Special Allowance
        
        # Verify: Total Gross = Basic + HRA + Special Allowance
        calculated_total_gross = basic_annual + hra_annual + special_allowance_annual
        
        # Note: Professional Tax and Other Tax are already subtracted from CTC to calculate Total Gross
        # They are NOT deducted again from Total Earnings
        # Employer PF is also NOT deducted from employee earnings (it's employer's contribution)
        
        # Step 8: Net Annual = Total Earnings (no additional deductions)
        # Since PT and Other Tax are already factored into Total Gross calculation
        net_annual = total_earnings_annual
        
        # Monthly In-Hand = Net Annual / 12
        monthly_in_hand = round(net_annual / 12, 2)
        
        # Verify CTC calculation: CTC = Total Gross + Employer PF + Variable Pay + Fixed Allowances + Fixed Deductions
        calculated_ctc = total_gross + employer_pf_annual + variable_pay_annual + fixed_allowances + fixed_deductions
        
        return {
            # Earnings (Employee receives these)
            "basic_annual": basic_annual,
            "hra_annual": hra_annual,
            "special_allowance_annual": special_allowance_annual,
            "conveyance_annual": conveyance_annual,
            "medical_allowance_annual": medical_annual,
            "other_allowance_annual": other_annual,
            "total_gross_annual": total_gross,  # Total Gross = Basic + HRA + Special Allowance
            
            # Variable pay (optional, manual)
            "variable_pay_annual": variable_pay_annual,
            
            # Employer contribution (subtracted from CTC, NOT deducted from employee)
            "employer_pf_annual": employer_pf_annual,
            
            # Statutory amounts (subtracted from CTC to calculate Total Gross, shown for reference)
            "professional_tax_annual": professional_tax_annual,
            "other_tax_annual": other_tax_annual,
            
            # Calculated totals
            "total_earnings_annual": total_earnings_annual,  # = Total Gross = Basic + HRA + Special
            "total_employee_deductions_annual": 0.0,  # No deductions from earnings (already in CTC breakdown)
            "total_employer_contributions_annual": employer_pf_annual,
            "net_annual": net_annual,  # = Total Earnings (no additional deductions)
            "ctc_annual": annual_ctc,
            "calculated_ctc": calculated_ctc,
            "monthly_ctc": round(annual_ctc / 12, 2),
            "monthly_gross": round(total_gross / 12, 2),
            "monthly_in_hand": monthly_in_hand,
            "monthly_variable_pay": round(variable_pay_annual / 12, 2) if variable_pay_annual > 0 else 0.0
        }
    
    @classmethod
    def _calculate_variable_pay(
        cls,
        annual_ctc: float,
        variable_pay_type: VariablePayType,
        variable_pay_value: float
    ) -> float:
        """Calculate variable pay based on type and value"""
        if variable_pay_type == VariablePayType.NONE:
            return 0.0
        elif variable_pay_type == VariablePayType.PERCENTAGE:
            if not (0 <= variable_pay_value <= 100):
                raise ValueError("Variable pay percentage must be between 0 and 100")
            return round(annual_ctc * (variable_pay_value / 100), 2)
        elif variable_pay_type == VariablePayType.FIXED:
            if variable_pay_value < 0:
                raise ValueError("Variable pay amount must be non-negative")
            return round(variable_pay_value, 2)
        else:
            raise ValueError(f"Invalid variable pay type: {variable_pay_type}")
    
    @classmethod
    def get_minimum_ctc(cls) -> float:
        """
        Get minimum CTC required for the fixed components.
        
        NEW Formula: CTC = Total Gross + Employer PF + Variable Pay + Fixed Allowances + Fixed Deductions
        Where: Total Gross = Basic + HRA + Special Allowance
               Basic = 50% of Total Gross
               HRA = 50% of Basic = 25% of Total Gross
               Special Allowance = 25% of Total Gross (remaining after fixed allowances)
               Employer PF = 12% of Basic = 6% of Total Gross
        
        Minimum CTC = Total Gross + Employer PF + Fixed Allowances + Fixed Deductions
        """
        fixed_allowances = cls.TOTAL_FIXED_ALLOWANCES  # ₹37,200
        fixed_deductions = cls.TOTAL_FIXED_DEDUCTIONS  # ₹14,400
        
        # Minimum Total Gross to have positive values
        min_total_gross = 1000.0  # Minimum ₹1,000 for Total Gross
        
        # Employer PF = 12% of Basic = 12% of 50% of Total Gross = 6% of Total Gross
        employer_pf = min_total_gross * cls.EMPLOYER_PF_PERCENTAGE * cls.BASIC_PERCENTAGE
        
        # Minimum CTC = Total Gross + Employer PF + Fixed Allowances + Fixed Deductions
        min_ctc = min_total_gross + employer_pf + fixed_allowances + fixed_deductions
        
        return round(min_ctc, 2)
    
    @classmethod
    def validate_ctc(cls, annual_ctc: float) -> bool:
        """Validate if CTC is sufficient for minimum components"""
        try:
            cls.calculate_salary_components(annual_ctc)
            return True
        except ValueError:
            return False
    
    @classmethod
    def get_salary_breakdown_summary(cls, annual_ctc: float) -> Dict[str, str]:
        """Get a human-readable summary of salary breakdown"""
        try:
            components = cls.calculate_salary_components(annual_ctc)
            
            return {
                "annual_ctc": f"₹{annual_ctc:,.2f}",
                "monthly_ctc": f"₹{components['monthly_ctc']:,.2f}",
                "basic_monthly": f"₹{components['basic_annual']/12:,.2f}",
                "hra_monthly": f"₹{components['hra_annual']/12:,.2f}",
                "special_allowance_monthly": f"₹{components['special_allowance_annual']/12:,.2f}",
                "medical_monthly": f"₹{components['medical_allowance_annual']/12:,.2f}",
                "conveyance_monthly": f"₹{components['conveyance_annual']/12:,.2f}",
                "other_monthly": f"₹{components['other_allowance_annual']/12:,.2f}",
                "professional_tax_monthly": f"₹{components['professional_tax_annual']/12:,.2f}",
                "monthly_in_hand": f"₹{components['monthly_in_hand']:,.2f}"
            }
        except ValueError as e:
            return {"error": str(e)}


def calculate_salary_from_ctc(
    annual_ctc: float,
    variable_pay_type: str = "none",
    variable_pay_value: float = 0.0,
    employer_pf_percentage: float = None,
    
    uan_number: Optional[str] = None,
    bank_name: Optional[str] = None,
    bank_account: Optional[str] = None,
    ifsc_code: Optional[str] = None,
    working_days_per_month: int = 22,
    payment_mode: str = "Bank Transfer"
) -> Dict[str, any]:
    """
    Main function to calculate salary components from CTC
    Returns a dictionary that can be used to create EmployeeSalary record
    
    Args:
        annual_ctc: Total annual CTC (Package)
        variable_pay_type: Type of variable pay (none/percentage/fixed)
        variable_pay_value: Value for variable pay
        employer_pf_percentage: Employer PF percentage (default 12%, editable)
        pan_number: PAN number
        uan_number: UAN number
        bank_name: Bank name
        bank_account: Bank account number
        ifsc_code: IFSC code
        working_days_per_month: Working days per month (default 22)
        payment_mode: Payment mode (default "Bank Transfer")
    """
    # Validate variable pay type
    try:
        vp_type = VariablePayType(variable_pay_type.lower())
    except ValueError:
        raise ValueError(f"Invalid variable pay type: {variable_pay_type}")
    
    # Calculate components
    components = SalaryCalculator.calculate_salary_components(
        annual_ctc, vp_type, variable_pay_value, employer_pf_percentage
    )
    
    # Return data structure compatible with EmployeeSalary model
    return {
        "basic_annual": components["basic_annual"],
        "hra_annual": components["hra_annual"],
        "special_allowance_annual": components["special_allowance_annual"],
        "conveyance_annual": components["conveyance_annual"],
        "medical_allowance_annual": components["medical_allowance_annual"],
        "other_allowance_annual": components["other_allowance_annual"],
        "professional_tax_annual": components["professional_tax_annual"],
        "other_deduction_annual": components["other_tax_annual"],  # Other Tax
        "pf_annual": components["employer_pf_annual"],  # Employer PF
        "variable_pay": components["variable_pay_annual"],
        
        "uan_number": uan_number,
        "bank_name": bank_name,
        "bank_account": bank_account,
        "ifsc_code": ifsc_code,
        "working_days_per_month": working_days_per_month,
        "payment_mode": payment_mode
    }