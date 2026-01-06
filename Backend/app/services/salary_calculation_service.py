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
    
    Fixed Components:
    - Basic = 50% of CTC
    - HRA = 50% of Basic
    - Medical = ₹19,200/year
    - Conveyance = ₹15,000/year
    - Other = ₹3,000/year
    - Special Allowance = Remaining amount to reach CTC
    - Professional Tax = ₹2,400/year (fixed deduction)
    """
    
    # Fixed annual amounts
    MEDICAL_ALLOWANCE_ANNUAL = 19200.0
    CONVEYANCE_ALLOWANCE_ANNUAL = 15000.0
    OTHER_ALLOWANCE_ANNUAL = 3000.0
    PROFESSIONAL_TAX_ANNUAL = 2400.0  # ₹200/month
    
    # Calculation percentages
    BASIC_PERCENTAGE = 0.50  # 50% of CTC
    HRA_PERCENTAGE = 0.50    # 50% of Basic
    
    @classmethod
    def calculate_salary_components(
        cls,
        annual_ctc: float,
        variable_pay_type: VariablePayType = VariablePayType.NONE,
        variable_pay_value: float = 0.0
    ) -> Dict[str, float]:
        """
        Calculate all salary components based on Annual CTC
        
        Args:
            annual_ctc: Total annual CTC amount
            variable_pay_type: Type of variable pay (none/percentage/fixed)
            variable_pay_value: Value for variable pay (percentage or fixed amount)
            
        Returns:
            Dictionary with all calculated salary components
        """
        if annual_ctc <= 0:
            raise ValueError("Annual CTC must be greater than 0")
        
        # Calculate basic salary (50% of CTC)
        basic_annual = round(annual_ctc * cls.BASIC_PERCENTAGE, 2)
        
        # Calculate HRA (50% of Basic)
        hra_annual = round(basic_annual * cls.HRA_PERCENTAGE, 2)
        
        # Fixed allowances
        medical_annual = cls.MEDICAL_ALLOWANCE_ANNUAL
        conveyance_annual = cls.CONVEYANCE_ALLOWANCE_ANNUAL
        other_annual = cls.OTHER_ALLOWANCE_ANNUAL
        
        # Calculate special allowance (remaining amount to reach CTC)
        fixed_components_total = (
            basic_annual + hra_annual + medical_annual + 
            conveyance_annual + other_annual
        )
        special_allowance_annual = round(annual_ctc - fixed_components_total, 2)
        
        # Ensure special allowance is not negative
        if special_allowance_annual < 0:
            raise ValueError(
                f"CTC amount {annual_ctc} is too low. "
                f"Minimum required CTC: {fixed_components_total}"
            )
        
        # Calculate variable pay
        variable_pay_annual = cls._calculate_variable_pay(
            annual_ctc, variable_pay_type, variable_pay_value
        )
        
        # Fixed deductions
        professional_tax_annual = cls.PROFESSIONAL_TAX_ANNUAL
        
        return {
            # Earnings
            "basic_annual": basic_annual,
            "hra_annual": hra_annual,
            "special_allowance_annual": special_allowance_annual,
            "conveyance_annual": conveyance_annual,
            "medical_allowance_annual": medical_annual,
            "other_allowance_annual": other_annual,
            
            # Variable pay (separate from regular salary)
            "variable_pay_annual": variable_pay_annual,
            
            # Deductions
            "professional_tax_annual": professional_tax_annual,
            
            # Calculated totals
            "total_earnings_annual": annual_ctc,
            "total_deductions_annual": professional_tax_annual,
            "net_annual": annual_ctc - professional_tax_annual,
            "monthly_ctc": round(annual_ctc / 12, 2),
            "monthly_in_hand": round((annual_ctc - professional_tax_annual) / 12, 2),
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
        """Get minimum CTC required for the fixed components"""
        return (
            cls.MEDICAL_ALLOWANCE_ANNUAL + 
            cls.CONVEYANCE_ALLOWANCE_ANNUAL + 
            cls.OTHER_ALLOWANCE_ANNUAL
        ) / (1 - cls.BASIC_PERCENTAGE - (cls.BASIC_PERCENTAGE * cls.HRA_PERCENTAGE))
    
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
    pan_number: Optional[str] = None,
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
    """
    # Validate variable pay type
    try:
        vp_type = VariablePayType(variable_pay_type.lower())
    except ValueError:
        raise ValueError(f"Invalid variable pay type: {variable_pay_type}")
    
    # Calculate components
    components = SalaryCalculator.calculate_salary_components(
        annual_ctc, vp_type, variable_pay_value
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
        "other_deduction_annual": 0.0,  # No other deductions by default
        "pf_annual": 0.0,  # PF can be added separately if needed
        "variable_pay": components["variable_pay_annual"],
        "pan_number": pan_number,
        "uan_number": uan_number,
        "bank_name": bank_name,
        "bank_account": bank_account,
        "ifsc_code": ifsc_code,
        "working_days_per_month": working_days_per_month,
        "payment_mode": payment_mode
    }