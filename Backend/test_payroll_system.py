"""
Test script for the new CTC-based payroll system
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.salary_calculation_service import SalaryCalculator, calculate_salary_from_ctc, VariablePayType


def test_salary_calculations():
    """Test various CTC amounts and variable pay configurations"""
    
    print("=== CTC-Based Payroll System Test ===\n")
    
    # Test cases
    test_cases = [
        {
            "name": "Basic CTC - 6 LPA",
            "ctc": 600000,
            "variable_pay_type": VariablePayType.NONE,
            "variable_pay_value": 0
        },
        {
            "name": "Mid-level CTC - 12 LPA",
            "ctc": 1200000,
            "variable_pay_type": VariablePayType.NONE,
            "variable_pay_value": 0
        },
        {
            "name": "Senior CTC - 18 LPA with 10% Variable Pay",
            "ctc": 1800000,
            "variable_pay_type": VariablePayType.PERCENTAGE,
            "variable_pay_value": 10
        },
        {
            "name": "Executive CTC - 25 LPA with Fixed Variable Pay",
            "ctc": 2500000,
            "variable_pay_type": VariablePayType.FIXED,
            "variable_pay_value": 100000
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"{i}. {case['name']}")
        print("-" * 50)
        
        try:
            components = SalaryCalculator.calculate_salary_components(
                case["ctc"], 
                case["variable_pay_type"], 
                case["variable_pay_value"]
            )
            
            print(f"Annual CTC: ₹{case['ctc']:,}")
            print(f"Monthly CTC: ₹{components['monthly_ctc']:,}")
            print()
            
            print("EARNINGS (Annual):")
            print(f"  Basic (50% of CTC): ₹{components['basic_annual']:,}")
            print(f"  HRA (50% of Basic): ₹{components['hra_annual']:,}")
            print(f"  Medical Allowance: ₹{components['medical_allowance_annual']:,}")
            print(f"  Conveyance: ₹{components['conveyance_annual']:,}")
            print(f"  Other Allowance: ₹{components['other_allowance_annual']:,}")
            print(f"  Special Allowance: ₹{components['special_allowance_annual']:,}")
            print(f"  Total Earnings: ₹{components['total_earnings_annual']:,}")
            print()
            
            if components['variable_pay_annual'] > 0:
                print("VARIABLE PAY:")
                print(f"  Annual Variable Pay: ₹{components['variable_pay_annual']:,}")
                print(f"  Monthly Variable Pay: ₹{components['monthly_variable_pay']:,}")
                print()
            
            print("DEDUCTIONS (Annual):")
            print(f"  Professional Tax: ₹{components['professional_tax_annual']:,}")
            print(f"  Total Deductions: ₹{components['total_deductions_annual']:,}")
            print()
            
            print("NET SALARY:")
            print(f"  Annual Net: ₹{components['net_annual']:,}")
            print(f"  Monthly In-Hand: ₹{components['monthly_in_hand']:,}")
            
        except ValueError as e:
            print(f"ERROR: {e}")
        
        print("\n" + "="*60 + "\n")


def test_minimum_ctc():
    """Test minimum CTC calculation"""
    print("=== Minimum CTC Test ===")
    min_ctc = SalaryCalculator.get_minimum_ctc()
    print(f"Minimum CTC required: ₹{min_ctc:,.2f}")
    
    # Test with minimum CTC
    try:
        components = SalaryCalculator.calculate_salary_components(min_ctc)
        print(f"Special Allowance at minimum CTC: ₹{components['special_allowance_annual']:,.2f}")
    except ValueError as e:
        print(f"Error with minimum CTC: {e}")
    
    # Test with CTC below minimum
    try:
        low_ctc = min_ctc - 10000
        SalaryCalculator.calculate_salary_components(low_ctc)
        print("ERROR: Should have failed with low CTC")
    except ValueError as e:
        print(f"Correctly rejected low CTC: {e}")
    
    print("\n" + "="*60 + "\n")


def test_variable_pay_validation():
    """Test variable pay validation"""
    print("=== Variable Pay Validation Test ===")
    
    ctc = 1000000
    
    # Test invalid percentage
    try:
        SalaryCalculator.calculate_salary_components(ctc, VariablePayType.PERCENTAGE, 150)
        print("ERROR: Should have failed with >100% variable pay")
    except ValueError as e:
        print(f"Correctly rejected invalid percentage: {e}")
    
    # Test negative fixed amount
    try:
        SalaryCalculator.calculate_salary_components(ctc, VariablePayType.FIXED, -5000)
        print("ERROR: Should have failed with negative variable pay")
    except ValueError as e:
        print(f"Correctly rejected negative amount: {e}")
    
    print("\n" + "="*60 + "\n")


def test_salary_breakdown_summary():
    """Test human-readable salary breakdown"""
    print("=== Salary Breakdown Summary Test ===")
    
    ctc = 1500000
    summary = SalaryCalculator.get_salary_breakdown_summary(ctc)
    
    print("Salary Breakdown Summary:")
    for key, value in summary.items():
        print(f"  {key.replace('_', ' ').title()}: {value}")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    test_salary_calculations()
    test_minimum_ctc()
    test_variable_pay_validation()
    test_salary_breakdown_summary()
    
    print("All tests completed!")