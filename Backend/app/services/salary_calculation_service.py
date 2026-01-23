"""
Salary Calculation Service - Automatic salary component calculations based on CTC

STRICT CALCULATION RULES (FINAL – LOCKED):

1. Total Gross =
   CTC − (Employer PF + Variable Pay + Medical + Conveyance + Other)

2. Basic = 50% of CTC
3. HRA = 50% of Basic

4. Special Allowance =
   (CTC − Variable Pay) − (Basic + HRA + Medical + Conveyance + Other + Professional Tax + Other Tax + PF)
   (If no variable pay is present, Variable Pay = 0 and the formula reduces to CTC − (...))

5. Total Earnings Annual = Total Gross ONLY

6. Employer PF is part of CTC, NEVER deducted from employee

    7. Monthly In-Hand =
   Total Earnings / 12  (Total Earnings = Total Gross)

CTC IDENTITY:
CTC =
Total Gross
+ Employer PF
 + Variable Pay
 + Medical
 + Conveyance
 + Other
 + Professional Tax
 + Other Tax
"""

from typing import Dict, Optional
from enum import Enum


# ======================================================
# ENUMS
# ======================================================

class VariablePayType(str, Enum):
    NONE = "none"
    PERCENTAGE = "percentage"
    FIXED = "fixed"


# ======================================================
# SALARY CALCULATOR
# ======================================================

class SalaryCalculator:

    # ---------- Fixed Annual Amounts ----------
    MEDICAL_ALLOWANCE_ANNUAL = 19200.0
    CONVEYANCE_ALLOWANCE_ANNUAL = 15000.0
    OTHER_ALLOWANCE_ANNUAL = 3000.0

    PROFESSIONAL_TAX_ANNUAL = 2400.0
    OTHER_TAX_ANNUAL = 12000.0

    EMPLOYER_PF_PERCENTAGE = 0.12   # 12% of Basic
    BASIC_PERCENTAGE = 0.50
    HRA_PERCENTAGE = 0.50

    # ==================================================

    @classmethod
    def calculate_salary_components(
        cls,
        annual_ctc: float,
        variable_pay_type: VariablePayType = VariablePayType.NONE,
        variable_pay_value: float = 0.0,
        employer_pf_percentage: float | None = None
    ) -> Dict[str, float]:

        if annual_ctc <= 0:
            raise ValueError("Annual CTC must be greater than 0")

        if employer_pf_percentage is None:
            employer_pf_percentage = cls.EMPLOYER_PF_PERCENTAGE

        # ---------- Variable Pay ----------
        variable_pay_annual = cls._calculate_variable_pay(
            annual_ctc, variable_pay_type, variable_pay_value
        )

        # ---------- Fixed Components ----------
        medical = cls.MEDICAL_ALLOWANCE_ANNUAL
        conveyance = cls.CONVEYANCE_ALLOWANCE_ANNUAL
        other = cls.OTHER_ALLOWANCE_ANNUAL

        professional_tax = cls.PROFESSIONAL_TAX_ANNUAL
        other_tax = cls.OTHER_TAX_ANNUAL

        # ---------- BASIC & EMPLOYER PF ----------
        # If variable pay is provided (fixed or percentage), deduct it from CTC
        # first and compute Basic as 50% of the remaining CTC. Otherwise Basic is
        # 50% of full CTC.
        if variable_pay_annual > 0:
            ctc_for_basic = annual_ctc - variable_pay_annual
        else:
            ctc_for_basic = annual_ctc

        basic = round(ctc_for_basic * cls.BASIC_PERCENTAGE, 2)
        hra = round(basic * cls.HRA_PERCENTAGE, 2)
        employer_pf = round(basic * employer_pf_percentage, 2)

        # ---------- TOTAL GROSS ----------
        # Total Gross = CTC − (Employer PF + Variable Pay + Medical + Conveyance + Other)
        total_gross = round(
            annual_ctc
            - employer_pf
            - variable_pay_annual
            - medical
            - conveyance
            - other,
            2
        )

        if total_gross <= 0:
            raise ValueError("CTC too low to calculate salary")

        # ---------- BREAKUP ----------
        hra = round(basic * cls.HRA_PERCENTAGE, 2)

        # Special Allowance is defined as the remainder of (CTC - variable_pay)
        # after subtracting components that are part of the CTC (basic, HRA,
        # fixed allowances, professional & other taxes, and employer PF).
        ctc_for_special = annual_ctc - variable_pay_annual if variable_pay_annual > 0 else annual_ctc

        special = round(
            ctc_for_special
            - (
                basic
                + hra
                + medical
                + conveyance
                + other
                + professional_tax
                + other_tax
                + employer_pf
            ),
            2
        )

        if special < 0:
            raise ValueError("Special Allowance became negative. Increase CTC.")

        # ---------- NET PAY ----------
        net_annual = total_gross - professional_tax - other_tax
        # Monthly in-hand now defined as total earnings (Total Gross) / 12
        monthly_in_hand = round(total_gross / 12, 2)

        # ---------- CTC RECONSTRUCTION ----------
        calculated_ctc = round(
            total_gross
            + employer_pf
            + variable_pay_annual
            + medical
            + conveyance
            + other,
            2
        )

        # ---------- HARD VALIDATIONS ----------
        # Reconstruct CTC to ensure arithmetic consistency.
        assert calculated_ctc == round(annual_ctc, 2), "CTC mismatch"

        return {
            # Earnings
            "basic_annual": basic,
            "hra_annual": hra,
            "special_allowance_annual": special,
            "medical_allowance_annual": medical,
            "conveyance_annual": conveyance,
            "other_allowance_annual": other,
            "total_gross_annual": total_gross,

            # Employer / CTC
            "employer_pf_annual": employer_pf,
            "variable_pay_annual": variable_pay_annual,

            # Deductions
            "professional_tax_annual": professional_tax,
            "other_tax_annual": other_tax,
            "total_deductions_annual": round(professional_tax + other_tax + employer_pf, 2),

            # Totals
            "total_earnings_annual": total_gross,
            "total_employee_deductions_annual": professional_tax + other_tax,
            "total_employer_contributions_annual": employer_pf,
            "net_annual": net_annual,
            "monthly_in_hand": monthly_in_hand,

            # CTC
            "package_ctc_annual": annual_ctc,
            "monthly_ctc": round(annual_ctc / 12, 2),
            "monthly_gross": round(total_gross / 12, 2),
            "monthly_variable_pay": round(variable_pay_annual / 12, 2),
        }

    # ==================================================

    @classmethod
    def _calculate_variable_pay(
        cls,
        annual_ctc: float,
        variable_pay_type: VariablePayType,
        variable_pay_value: float
    ) -> float:

        if variable_pay_type == VariablePayType.NONE:
            return 0.0

        if variable_pay_type == VariablePayType.PERCENTAGE:
            if not (0 <= variable_pay_value <= 100):
                raise ValueError("Variable pay percentage must be between 0 and 100")
            return round(annual_ctc * variable_pay_value / 100, 2)

        if variable_pay_type == VariablePayType.FIXED:
            if variable_pay_value < 0:
                raise ValueError("Variable pay must be >= 0")
            return round(variable_pay_value, 2)

        raise ValueError("Invalid variable pay type")


# ======================================================
# PUBLIC FUNCTION (USED BY CRUD / ROUTES)
# ======================================================

def calculate_salary_from_ctc(
    annual_ctc: float,
    variable_pay_type: str = "none",
    variable_pay_value: float = 0.0,
    employer_pf_percentage: float | None = None,
    uan_number: Optional[str] = None,
    bank_name: Optional[str] = None,
    bank_account: Optional[str] = None,
    ifsc_code: Optional[str] = None,
    working_days_per_month: int = 22,
    payment_mode: str = "Bank Transfer"
) -> Dict[str, any]:

    vp_type = VariablePayType(variable_pay_type.lower())

    components = SalaryCalculator.calculate_salary_components(
        annual_ctc,
        vp_type,
        variable_pay_value,
        employer_pf_percentage
    )

    return {
        "basic_annual": components["basic_annual"],
        "hra_annual": components["hra_annual"],
        "special_allowance_annual": components["special_allowance_annual"],
        "medical_allowance_annual": components["medical_allowance_annual"],
        "conveyance_annual": components["conveyance_annual"],
        "other_allowance_annual": components["other_allowance_annual"],
        "professional_tax_annual": components["professional_tax_annual"],
        "other_deduction_annual": components["other_tax_annual"],
        "pf_annual": components["employer_pf_annual"],
        "variable_pay": components["variable_pay_annual"],
        "uan_number": uan_number,
        "bank_name": bank_name,
        "bank_account": bank_account,
        "ifsc_code": ifsc_code,
        "working_days_per_month": working_days_per_month,
        "payment_mode": payment_mode,
    }
