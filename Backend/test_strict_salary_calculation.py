"""
Test script to verify STRICT salary calculation rules.

STRICT CALCULATION RULES (as provided by user):
1. Total Gross = CTC − (Employer PF + Variable Pay + Medical ₹19,200 + Conveyance ₹15,000 + Other ₹3,000 + Professional Tax ₹2,400 + Other Tax ₹12,000)
2. Basic = 50% of Total Gross
3. HRA = 50% of Basic
4. Special Allowance = Total Gross − (Basic + HRA + Medical + Conveyance + Other)
5. Total Earnings Annual MUST equal Total Gross only
6. Employer PF is part of CTC, NEVER deducted from employee
7. Monthly In-Hand = (Total Gross − Professional Tax − Other Tax) / 12

INTERPRETATION:
- Rule 1: Medical, Conveyance, Other are subtracted from CTC to get Total Gross
- Rule 4: Special Allowance = Total Gross - Basic - HRA - Medical - Conveyance - Other
- This means Total Gross = Basic + HRA + Special Allowance (NOT including Medical, Conveyance, Other)
- CTC = Total Gross + Employer PF + Variable Pay + Medical + Conveyance + Other + PT + Other Tax
"""

import sys
sys.path.insert(0, '.')

from app.services.salary_calculation_service import SalaryCalculator, VariablePayType


def test_strict_calculation(ctc: float, variable_pay: float = 0.0):
    """Test salary calculation with strict rules verification"""
    print(f"\n{'='*60}")
    print(f"Testing CTC: ₹{ctc:,.2f}")
    if variable_pay > 0:
        print(f"Variable Pay: ₹{variable_pay:,.2f}")
    print('='*60)
    
    # Fixed values
    MEDICAL = 19200.0
    CONVEYANCE = 15000.0
    OTHER = 3000.0
    PT = 2400.0
    OTHER_TAX = 12000.0
    
    # Calculate components
    vp_type = VariablePayType.FIXED if variable_pay > 0 else VariablePayType.NONE
    components = SalaryCalculator.calculate_salary_components(
        annual_ctc=ctc,
        variable_pay_type=vp_type,
        variable_pay_value=variable_pay
    )
    
    # Extract values
    total_gross = components['total_gross_annual']
    basic = components['basic_annual']
    hra = components['hra_annual']
    special = components['special_allowance_annual']
    medical = components['medical_allowance_annual']
    conveyance = components['conveyance_annual']
    other = components['other_allowance_annual']
    employer_pf = components['employer_pf_annual']
    pt = components['professional_tax_annual']
    other_tax = components['other_tax_annual']
    variable = components['variable_pay_annual']
    total_earnings = components['total_earnings_annual']
    monthly_in_hand = components['monthly_in_hand']
    
    print("\n--- EARNINGS ---")
    print(f"Basic (50% of Total Gross):     ₹{basic:>12,.2f}")
    print(f"HRA (50% of Basic):             ₹{hra:>12,.2f}")
    print(f"Special Allowance:              ₹{special:>12,.2f}")
    print(f"                                 {'-'*14}")
    print(f"TOTAL GROSS:                    ₹{total_gross:>12,.2f}")
    
    print("\n--- FIXED ALLOWANCES (Part of CTC) ---")
    print(f"Medical Allowance:              ₹{medical:>12,.2f}")
    print(f"Conveyance Allowance:           ₹{conveyance:>12,.2f}")
    print(f"Other Allowance:                ₹{other:>12,.2f}")
    
    print("\n--- CTC COMPONENTS ---")
    print(f"Employer PF (12% of Basic):     ₹{employer_pf:>12,.2f}")
    print(f"Variable Pay:                   ₹{variable:>12,.2f}")
    print(f"Professional Tax:               ₹{pt:>12,.2f}")
    print(f"Other Tax:                      ₹{other_tax:>12,.2f}")
    
    print("\n--- VERIFICATION ---")
    
    # Rule 1: Total Gross = CTC − (Employer PF + Variable Pay + Medical + Conveyance + Other + PT + Other Tax)
    expected_total_gross = ctc - employer_pf - variable - MEDICAL - CONVEYANCE - OTHER - PT - OTHER_TAX
    rule1_pass = abs(total_gross - expected_total_gross) < 1
    print(f"Rule 1 - Total Gross Formula: {'✓ PASS' if rule1_pass else '✗ FAIL'}")
    if not rule1_pass:
        print(f"  Expected: ₹{expected_total_gross:,.2f}, Got: ₹{total_gross:,.2f}")
    
    # Rule 2: Basic = 50% of Total Gross
    expected_basic = total_gross * 0.50
    rule2_pass = abs(basic - expected_basic) < 1
    print(f"Rule 2 - Basic = 50% of Total Gross: {'✓ PASS' if rule2_pass else '✗ FAIL'}")
    if not rule2_pass:
        print(f"  Expected: ₹{expected_basic:,.2f}, Got: ₹{basic:,.2f}")
    
    # Rule 3: HRA = 50% of Basic
    expected_hra = basic * 0.50
    rule3_pass = abs(hra - expected_hra) < 1
    print(f"Rule 3 - HRA = 50% of Basic: {'✓ PASS' if rule3_pass else '✗ FAIL'}")
    if not rule3_pass:
        print(f"  Expected: ₹{expected_hra:,.2f}, Got: ₹{hra:,.2f}")
    
    # Rule 4: Special Allowance = Total Gross − (Basic + HRA + Medical + Conveyance + Other)
    # Since Medical, Conveyance, Other are NOT in Total Gross, this simplifies to:
    # Special Allowance = Total Gross - Basic - HRA
    expected_special = total_gross - basic - hra - MEDICAL - CONVEYANCE - OTHER
    rule4_pass = abs(special - expected_special) < 1
    print(f"Rule 4 - Special Allowance Formula: {'✓ PASS' if rule4_pass else '✗ FAIL'}")
    if not rule4_pass:
        print(f"  Expected: ₹{expected_special:,.2f}, Got: ₹{special:,.2f}")
    
    # Rule 5: Total Earnings = Total Gross
    rule5_pass = abs(total_earnings - total_gross) < 1
    print(f"Rule 5 - Total Earnings = Total Gross: {'✓ PASS' if rule5_pass else '✗ FAIL'}")
    if not rule5_pass:
        print(f"  Expected: ₹{total_gross:,.2f}, Got: ₹{total_earnings:,.2f}")
    
    # Verify Total Gross = Basic + HRA + Special (NOT including Medical, Conveyance, Other)
    calculated_gross = basic + hra + special
    gross_sum_pass = abs(calculated_gross - total_gross) < 1
    print(f"Total Gross = Basic + HRA + Special: {'✓ PASS' if gross_sum_pass else '✗ FAIL'}")
    if not gross_sum_pass:
        print(f"  Expected: ₹{total_gross:,.2f}, Got: ₹{calculated_gross:,.2f}")
    
    # Rule 7: Monthly In-Hand = (Total Gross − PT − Other Tax) / 12
    expected_monthly_in_hand = (total_gross - PT - OTHER_TAX) / 12
    rule7_pass = abs(monthly_in_hand - expected_monthly_in_hand) < 1
    print(f"Rule 7 - Monthly In-Hand Formula: {'✓ PASS' if rule7_pass else '✗ FAIL'}")
    if not rule7_pass:
        print(f"  Expected: ₹{expected_monthly_in_hand:,.2f}, Got: ₹{monthly_in_hand:,.2f}")
    
    # Verify CTC reconstruction: CTC = Total Gross + Employer PF + Variable Pay + Medical + Conveyance + Other + PT + Other Tax
    reconstructed_ctc = total_gross + employer_pf + variable + MEDICAL + CONVEYANCE + OTHER + PT + OTHER_TAX
    ctc_match = abs(reconstructed_ctc - ctc) < 1
    print(f"CTC Reconstruction: {'✓ PASS' if ctc_match else '✗ FAIL'}")
    if not ctc_match:
        print(f"  Expected: ₹{ctc:,.2f}, Got: ₹{reconstructed_ctc:,.2f}")
    
    print("\n--- SUMMARY ---")
    print(f"Annual CTC:                     ₹{ctc:>12,.2f}")
    print(f"Annual Total Gross:             ₹{total_gross:>12,.2f}")
    print(f"Annual Net (after deductions):  ₹{total_gross - PT - OTHER_TAX:>12,.2f}")
    print(f"Monthly In-Hand:                ₹{monthly_in_hand:>12,.2f}")
    
    all_pass = all([rule1_pass, rule2_pass, rule3_pass, rule4_pass, rule5_pass, gross_sum_pass, rule7_pass, ctc_match])
    return all_pass


def main():
    print("="*60)
    print("STRICT SALARY CALCULATION VERIFICATION")
    print("="*60)
    
    # Test cases
    test_cases = [
        (300000, 0),      # ₹3 LPA, no variable
        (500000, 0),      # ₹5 LPA, no variable
        (600000, 0),      # ₹6 LPA, no variable
        (800000, 0),      # ₹8 LPA, no variable
        (1000000, 0),     # ₹10 LPA, no variable
        (1200000, 0),     # ₹12 LPA, no variable
        (500000, 50000),  # ₹5 LPA with ₹50K variable
    ]
    
    results = []
    for ctc, variable in test_cases:
        try:
            passed = test_strict_calculation(ctc, variable)
            results.append((ctc, variable, passed))
        except ValueError as e:
            print(f"\n{'='*60}")
            print(f"CTC ₹{ctc:,.2f} - ERROR: {e}")
            results.append((ctc, variable, False))
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    for ctc, variable, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        vp_str = f" + ₹{variable:,.0f} VP" if variable > 0 else ""
        print(f"CTC ₹{ctc:>10,.0f}{vp_str}: {status}")
    
    all_passed = all(r[2] for r in results)
    print("\n" + "="*60)
    print(f"OVERALL: {'ALL TESTS PASSED ✓' if all_passed else 'SOME TESTS FAILED ✗'}")
    print("="*60)


if __name__ == "__main__":
    main()
