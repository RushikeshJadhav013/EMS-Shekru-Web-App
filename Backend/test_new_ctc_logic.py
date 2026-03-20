"""
Test script to verify the new CTC salary calculation logic.

NEW Formula (updated for current calculator):
1. Basic = 50% of CTC
2. HRA = 50% of Basic
3. Employer PF = 12% of Basic
4. Special Allowance = CTC − (Basic + HRA + Medical + Conveyance + Other)
5. Total Gross = Basic + HRA + Medical + Conveyance + Other + Special
6. Total Earnings (Annual) = Total Gross
"""

import sys
sys.path.insert(0, '.')

from app.services.salary_calculation_service import SalaryCalculator, calculate_salary_from_ctc

def test_ctc_calculation(ctc: float):
    """Test CTC calculation with the new formula"""
    print(f"\n{'='*60}")
    print(f"Testing CTC: ₹{ctc:,.2f}")
    print('='*60)
    
    components = SalaryCalculator.calculate_salary_components(ctc)
    
    # Fixed values
    medical = 13200.0
    conveyance = 15000.0
    other = 3000.0
    professional_tax = 2500.0
    other_tax = 12000.0
    fixed_allowances = medical + conveyance + other  # ₹37,200
    fixed_deductions = professional_tax + other_tax  # ₹14,400
    
    print("\n--- Calculated Components ---")
    print(f"Basic (Annual):              ₹{components['basic_annual']:,.2f}")
    print(f"HRA (Annual):                ₹{components['hra_annual']:,.2f}")
    print(f"Special Allowance (Annual):  ₹{components['special_allowance_annual']:,.2f}")
    print(f"Medical Allowance (Annual):  ₹{components['medical_allowance_annual']:,.2f}")
    print(f"Conveyance (Annual):         ₹{components['conveyance_annual']:,.2f}")
    print(f"Other Allowance (Annual):    ₹{components['other_allowance_annual']:,.2f}")
    print(f"Employer PF (Annual):        ₹{components['employer_pf_annual']:,.2f}")
    
    print("\n--- Totals ---")
    print(f"Total Gross (Annual):        ₹{components['total_gross_annual']:,.2f}")
    print(f"Total Earnings (Annual):     ₹{components['total_earnings_annual']:,.2f}")
    print(f"Net Annual:                  ₹{components['net_annual']:,.2f}")
    print(f"Monthly In-Hand:             ₹{components['monthly_in_hand']:,.2f}")
    
    print("\n--- Verification ---")
    # Verify: Special and Total Gross per formula
    basic = components["basic_annual"]
    hra = components["hra_annual"]
    employer_pf = components["employer_pf_annual"]

    expected_special = ctc - (
        basic + hra + medical + conveyance + other
    )
    print(f"Expected Special:             ₹{expected_special:,.2f}")
    print(f"Special matches formula:     {abs(components['special_allowance_annual'] - expected_special) < 0.01}")

    calculated_total_gross = (
        basic + hra + medical + conveyance + other + components["special_allowance_annual"]
    )
    print(f"TotalGross per formula:      ₹{calculated_total_gross:,.2f}")
    print(f"Total gross matches formula: {abs(components['total_gross_annual'] - calculated_total_gross) < 0.01}")
    
    # Verify: Total Earnings = Total Gross
    print(f"Total Earnings = Total Gross: {abs(components['total_earnings_annual'] - components['total_gross_annual']) < 0.01}")
    
    # Verify: Basic = 50% of CTC
    expected_basic = ctc * 0.50
    print(f"Basic = 50% of CTC:          {abs(components['basic_annual'] - expected_basic) < 0.01}")
    
    # Verify: HRA = 50% of Basic
    expected_hra = components['basic_annual'] * 0.50
    print(f"HRA = 50% of Basic:          {abs(components['hra_annual'] - expected_hra) < 0.01}")
    
    # Verify: (with requested formulas) Total Gross equals input CTC
    reconstructed_ctc = components["total_gross_annual"]
    print(f"Reconstructed CTC:           ₹{reconstructed_ctc:,.2f}")
    print(f"Original CTC:                ₹{ctc:,.2f}")
    print(f"CTC matches:                 {abs(reconstructed_ctc - ctc) < 1.0}")
    
    # Verify: Employee deductions include PF (PT + Other Tax + PF)
    expected_employee_deductions = professional_tax + other_tax + employer_pf
    print(f"Employee Deductions:         ₹{components['total_employee_deductions_annual']:,.2f}")
    print(f"Matches (PT + OtherTax + PF): {abs(components['total_employee_deductions_annual'] - expected_employee_deductions) < 0.01}")
    
    return components

if __name__ == "__main__":
    # Test with different CTC values
    test_cases = [300000, 500000, 800000, 1200000]
    
    for ctc in test_cases:
        test_ctc_calculation(ctc)
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)
