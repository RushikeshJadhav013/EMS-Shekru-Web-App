"""
Test script for CTC-based salary calculation API
Demonstrates the automatic salary breakup calculation from Annual CTC
"""
import requests
import json
from typing import Dict

BASE_URL = "http://127.0.0.1:8000"

# Test data
TEST_CTC = 600000.0  # ₹6,00,000 annual CTC
TEST_USER_ID = 1


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def test_preview_calculation():
    """Test the salary calculation preview endpoint"""
    print_section("TEST 1: Preview Salary Calculation (No Save)")
    
    params = {
        "annual_ctc": TEST_CTC,
        "variable_pay_type": "none",
        "variable_pay_value": 0.0,
        "employer_pf_percentage": 12.0
    }
    
    print(f"Request Parameters:")
    print(f"  Annual CTC: ₹{params['annual_ctc']:,.2f}")
    print(f"  Variable Pay Type: {params['variable_pay_type']}")
    print(f"  Employer PF: {params['employer_pf_percentage']}%")
    
    try:
        response = requests.post(
            f"{BASE_URL}/salary/calculate-preview",
            params=params,
            headers={"Authorization": "Bearer YOUR_TOKEN"}  # Add your auth token
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ Preview Calculation Successful\n")
            
            print("SALARY BREAKDOWN:")
            print(f"  Annual CTC (Package):           ₹{data['annual_ctc']:>12,.2f}")
            print(f"  Total Gross Annual:             ₹{data['total_gross_annual']:>12,.2f}")
            print(f"  Employer PF (12% of Basic):     ₹{data['employer_pf_annual']:>12,.2f}")
            print(f"  Variable Pay:                   ₹{data['variable_pay_annual']:>12,.2f}")
            
            print(f"\nSALARY COMPONENTS (Annual):")
            print(f"  Basic (50% of Gross):           ₹{data['basic_annual']:>12,.2f}")
            print(f"  HRA (50% of Basic):             ₹{data['hra_annual']:>12,.2f}")
            print(f"  Special Allowance:              ₹{data['special_allowance_annual']:>12,.2f}")
            print(f"  Medical Allowance (Fixed):      ₹{data['medical_allowance_annual']:>12,.2f}")
            print(f"  Conveyance Allowance (Fixed):   ₹{data['conveyance_annual']:>12,.2f}")
            print(f"  Other Allowance (Fixed):        ₹{data['other_allowance_annual']:>12,.2f}")
            
            print(f"\nDEDUCTIONS (Annual):")
            print(f"  Professional Tax (₹200/month, Feb ₹300):  ₹{data['professional_tax_annual']:>12,.2f}")
            print(f"  Other Tax (₹1000/month):        ₹{data['other_tax_annual']:>12,.2f}")
            
            print(f"\nMONTHLY BREAKDOWN:")
            print(f"  Monthly CTC:                    ₹{data['monthly_ctc']:>12,.2f}")
            print(f"  Monthly Gross:                  ₹{data['monthly_gross']:>12,.2f}")
            print(f"  Monthly Basic:                  ₹{data['monthly_basic']:>12,.2f}")
            print(f"  Monthly HRA:                    ₹{data['monthly_hra']:>12,.2f}")
            print(f"  Monthly Professional Tax:       ₹{data['monthly_professional_tax']:>12,.2f}")
            print(f"  Monthly Other Tax:              ₹{data['monthly_other_tax']:>12,.2f}")
            print(f"  Monthly Employer PF:            ₹{data['monthly_employer_pf']:>12,.2f}")
            print(f"  Monthly In-Hand:                ₹{data['monthly_in_hand']:>12,.2f}")
            
            print(f"\nSUMMARY:")
            print(f"  Total Earnings (Annual):        ₹{data['total_earnings_annual']:>12,.2f}")
            print(f"  Total Employee Deductions:      ₹{data['total_employee_deductions_annual']:>12,.2f}")
            print(f"  Total Employer Contributions:   ₹{data['total_employer_contributions_annual']:>12,.2f}")
            print(f"  Net Annual (After Deductions):  ₹{data['net_annual']:>12,.2f}")
            
            return data
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"✗ Exception: {str(e)}")
        return None


def test_create_salary_from_ctc():
    """Test creating a salary record from CTC"""
    print_section("TEST 2: Create Salary Record from CTC")
    
    payload = {
        "user_id": TEST_USER_ID,
        "annual_ctc": TEST_CTC,
        "variable_pay_type": "none",
        "variable_pay_value": 0.0,
        "employer_pf_percentage": 12.0,
        "pan_number": "ABCDE1234F",
        "uan_number": "100123456789",
        "bank_name": "HDFC Bank",
        "bank_account": "1234567890123456",
        "ifsc_code": "HDFC0001234",
        "working_days_per_month": 22,
        "payment_mode": "Bank Transfer"
    }
    
    print(f"Request Payload:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(
            f"{BASE_URL}/salary/employee/from-ctc",
            json=payload,
            headers={"Authorization": "Bearer YOUR_TOKEN"}  # Add your auth token
        )
        
        if response.status_code == 201:
            data = response.json()
            print(f"\n✓ Salary Record Created Successfully\n")
            print(f"Salary ID: {data['id']}")
            print(f"User ID: {data['user_id']}")
            print(f"Monthly In-Hand: ₹{data['monthly_in_hand']:,.2f}")
            return data
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"✗ Exception: {str(e)}")
        return None


def test_with_variable_pay():
    """Test calculation with variable pay"""
    print_section("TEST 3: Calculation with Variable Pay (10% of CTC)")
    
    params = {
        "annual_ctc": TEST_CTC,
        "variable_pay_type": "percentage",
        "variable_pay_value": 10.0,  # 10% of CTC
        "employer_pf_percentage": 12.0
    }
    
    print(f"Request Parameters:")
    print(f"  Annual CTC: ₹{params['annual_ctc']:,.2f}")
    print(f"  Variable Pay: {params['variable_pay_value']}% of CTC")
    print(f"  Employer PF: {params['employer_pf_percentage']}%")
    
    try:
        response = requests.post(
            f"{BASE_URL}/salary/calculate-preview",
            params=params,
            headers={"Authorization": "Bearer YOUR_TOKEN"}  # Add your auth token
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ Calculation with Variable Pay Successful\n")
            
            print("KEY FIGURES:")
            print(f"  Annual CTC:                     ₹{data['annual_ctc']:>12,.2f}")
            print(f"  Variable Pay (10%):             ₹{data['variable_pay_annual']:>12,.2f}")
            print(f"  Total Gross (after var pay):    ₹{data['total_gross_annual']:>12,.2f}")
            print(f"  Monthly In-Hand:                ₹{data['monthly_in_hand']:>12,.2f}")
            
            return data
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"✗ Exception: {str(e)}")
        return None


def test_with_custom_employer_pf():
    """Test calculation with custom employer PF percentage"""
    print_section("TEST 4: Calculation with Custom Employer PF (15%)")
    
    params = {
        "annual_ctc": TEST_CTC,
        "variable_pay_type": "none",
        "variable_pay_value": 0.0,
        "employer_pf_percentage": 15.0  # Custom 15% instead of default 12%
    }
    
    print(f"Request Parameters:")
    print(f"  Annual CTC: ₹{params['annual_ctc']:,.2f}")
    print(f"  Employer PF: {params['employer_pf_percentage']}% (custom)")
    
    try:
        response = requests.post(
            f"{BASE_URL}/salary/calculate-preview",
            params=params,
            headers={"Authorization": "Bearer YOUR_TOKEN"}  # Add your auth token
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ Calculation with Custom Employer PF Successful\n")
            
            print("KEY FIGURES:")
            print(f"  Annual CTC:                     ₹{data['annual_ctc']:>12,.2f}")
            print(f"  Employer PF (15% of Basic):     ₹{data['employer_pf_annual']:>12,.2f}")
            print(f"  Total Gross:                    ₹{data['total_gross_annual']:>12,.2f}")
            print(f"  Monthly In-Hand:                ₹{data['monthly_in_hand']:>12,.2f}")
            
            return data
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"✗ Exception: {str(e)}")
        return None


def test_minimum_ctc():
    """Test getting minimum CTC requirement"""
    print_section("TEST 5: Get Minimum CTC Requirement")
    
    try:
        response = requests.get(
            f"{BASE_URL}/salary/minimum-ctc",
            headers={"Authorization": "Bearer YOUR_TOKEN"}  # Add your auth token
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Minimum CTC Retrieved\n")
            print(f"Minimum CTC Required: ₹{data['minimum_ctc']:,.2f}")
            print(f"\nFixed Components:")
            for key, value in data['components'].items():
                print(f"  {key}: {value}")
            
            return data
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"✗ Exception: {str(e)}")
        return None


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("  CTC-BASED SALARY CALCULATION API TEST SUITE")
    print("="*80)
    print("\nNote: Replace 'YOUR_TOKEN' with actual authentication token")
    print("Note: Replace TEST_USER_ID with actual user ID")
    
    # Run tests
    test_preview_calculation()
    test_with_variable_pay()
    test_with_custom_employer_pf()
    test_minimum_ctc()
    # test_create_salary_from_ctc()  # Uncomment to test creation
    
    print("\n" + "="*80)
    print("  TEST SUITE COMPLETED")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
