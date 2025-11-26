#!/usr/bin/env python3
"""
Test script to demonstrate duplicate validation for phone, PAN, and Aadhar
"""
import sys
sys.path.append('.')

def test_validation_logic():
    """Test the validation logic for duplicates"""
    
    print("=" * 60)
    print("DUPLICATE VALIDATION TEST")
    print("=" * 60)
    
    # Simulate database records
    existing_records = [
        {
            'employee_id': 'EMP001',
            'name': 'John Doe',
            'phone': '+91-9876543210',
            'pan_card': 'ABCDE1234F',
            'aadhar_card': '1234-5678-9012'
        },
        {
            'employee_id': 'EMP002',
            'name': 'Jane Smith',
            'phone': '+91-9876543211',
            'pan_card': 'BCDEF2345G',
            'aadhar_card': '2345-6789-0123'
        }
    ]
    
    # Test cases
    test_cases = [
        {
            'name': 'Test 1: Create with duplicate phone',
            'new_record': {
                'phone': '+91-9876543210',
                'pan_card': 'CDEFG3456H',
                'aadhar_card': '3456-7890-1234'
            },
            'expected_error': 'Phone number already exists'
        },
        {
            'name': 'Test 2: Create with duplicate PAN',
            'new_record': {
                'phone': '+91-9876543212',
                'pan_card': 'ABCDE1234F',
                'aadhar_card': '3456-7890-1234'
            },
            'expected_error': 'PAN Card already exists'
        },
        {
            'name': 'Test 3: Create with duplicate Aadhar',
            'new_record': {
                'phone': '+91-9876543212',
                'pan_card': 'CDEFG3456H',
                'aadhar_card': '1234-5678-9012'
            },
            'expected_error': 'Aadhar Card already exists'
        },
        {
            'name': 'Test 4: Create with all unique values',
            'new_record': {
                'phone': '+91-9876543212',
                'pan_card': 'CDEFG3456H',
                'aadhar_card': '3456-7890-1234'
            },
            'expected_error': None
        },
        {
            'name': 'Test 5: Case-insensitive PAN check',
            'new_record': {
                'phone': '+91-9876543212',
                'pan_card': 'abcde1234f',  # lowercase
                'aadhar_card': '3456-7890-1234'
            },
            'expected_error': 'PAN Card already exists'
        }
    ]
    
    print("\nRunning validation tests...\n")
    
    for test in test_cases:
        print(f"📋 {test['name']}")
        print(f"   New Record: {test['new_record']}")
        
        # Check for duplicates
        errors = []
        
        # Check phone
        for record in existing_records:
            if record['phone'] == test['new_record']['phone']:
                errors.append('Phone number already exists')
                break
        
        # Check PAN (case-insensitive)
        for record in existing_records:
            if record['pan_card'].upper() == test['new_record']['pan_card'].upper():
                errors.append('PAN Card already exists')
                break
        
        # Check Aadhar
        for record in existing_records:
            if record['aadhar_card'] == test['new_record']['aadhar_card']:
                errors.append('Aadhar Card already exists')
                break
        
        if errors:
            print(f"   ❌ Validation Failed: {', '.join(errors)}")
            if test['expected_error']:
                if any(test['expected_error'] in error for error in errors):
                    print(f"   ✅ Expected error detected correctly")
                else:
                    print(f"   ⚠️  Unexpected error (expected: {test['expected_error']})")
            else:
                print(f"   ⚠️  Unexpected validation failure")
        else:
            print(f"   ✅ Validation Passed - No duplicates found")
            if test['expected_error']:
                print(f"   ⚠️  Expected error not detected: {test['expected_error']}")
        
        print()
    
    print("=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)
    print("\n📝 Summary:")
    print("   - Phone numbers must be unique")
    print("   - PAN cards must be unique (case-insensitive)")
    print("   - Aadhar cards must be unique")
    print("   - Validation happens before database insertion")
    print("   - Errors are shown below the input fields in the UI")
    print()

if __name__ == "__main__":
    test_validation_logic()
