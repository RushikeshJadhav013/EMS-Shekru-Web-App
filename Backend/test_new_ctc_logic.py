"""
Test script to verify the new CTC salary calculation logic.

NEW Formula:
1. Total Gross = CTC − (Employer PF + Variable Pay + Medical ₹19,200 + Conveyance ₹15,000 + Other ₹3,000 + Professional Tax ₹2,400 + Other Tax ₹12,000)
2. Basic = 50% of Total Gross
3. HRA = 50% of Basic
4. Special Allowance = Total Gross − (Basic + HRA + all fixed allowances)
5. Total Earnings (Annual) = Total Gross
6. Employer PF is NOT double-counted in deductions
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
    medical = 19200.0
    conveyance = 15000.0
    other = 3000.0
    professional_tax = 2400.0
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
    # Verify: Total Gross = Basic + HRA + Special Allowance
    calculated_total_gross = (
        components['basic_annual'] + 
        components['hra_annual'] + 
        components['special_allowance_annual']
    )
    print(f"Calculated Total Gross:      ₹{calculated_total_gross:,.2f}")
    print(f"Total Gross = Basic+HRA+Special: {abs(calculated_total_gross - components['total_gross_annual']) < 0.01}")
    
    # Verify: Total Earnings = Total Gross
    print(f"Total Earnings = Total Gross: {abs(components['total_earnings_annual'] - components['total_gross_annual']) < 0.01}")
    
    # Verify: Basic = 50% of Total Gross
    expected_basic = components['total_gross_annual'] * 0.50
    print(f"Basic = 50% of Total Gross:  {abs(components['basic_annual'] - expected_basic) < 0.01}")
    
    # Verify: HRA = 50% of Basic
    expected_hra = components['basic_annual'] * 0.50
    print(f"HRA = 50% of Basic:          {abs(components['hra_annual'] - expected_hra) < 0.01}")
    
    # Verify: CTC = Total Gross + Employer PF + Variable Pay + Fixed Allowances + Fixed Deductions
    reconstructed_ctc = (
        components['total_gross_annual'] + 
        components['employer_pf_annual'] + 
        components['variable_pay_annual'] +
        fixed_allowances +
        fixed_deductions
    )
    print(f"Reconstructed CTC:           ₹{reconstructed_ctc:,.2f}")
    print(f"Original CTC:                ₹{ctc:,.2f}")
    print(f"CTC matches:                 {abs(reconstructed_ctc - ctc) < 1.0}")
    
    # Verify: Employer PF is NOT in deductions
    print(f"Employee Deductions:         ₹{components['total_employee_deductions_annual']:,.2f}")
    print(f"Employer PF NOT in deductions: {components['total_employee_deductions_annual'] == 0.0}")
    
    return components

if __name__ == "__main__":
    # Test with different CTC values
    test_cases = [300000, 500000, 800000, 1200000]
    
    for ctc in test_cases:
        test_ctc_calculation(ctc)
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)
