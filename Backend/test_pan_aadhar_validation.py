#!/usr/bin/env python3
"""
Test script to verify PAN and Aadhar validation logic
"""
import sys
sys.path.append('.')

def test_pan_aadhar_logic():
    """Test the PAN and Aadhar validation logic"""
    
    # Test PAN card normalization
    test_cases = [
        ('ABCDE1234F', 'ABCDE1234F', True),   # Same PAN should match
        ('abcde1234f', 'ABCDE1234F', True),   # Case insensitive should match
        ('ABCDE1234F', 'ABCDE1234G', False),  # Different PANs should not match
        ('', '', True),                       # Empty strings should match
        (None, None, True),                   # None values should match
        ('ABCDE1234F', '', False),            # Different values should not match
    ]
    
    print("Testing PAN card comparison logic:")
    for i, (pan1, pan2, expected) in enumerate(test_cases, 1):
        # Simulate the logic from get_user_by_pan_card
        if not pan1:
            result1 = None
        else:
            result1 = pan1.strip().upper()
            
        if not pan2:
            result2 = None
        else:
            result2 = pan2.strip().upper()
            
        actual = (result1 == result2)
        status = "✓" if actual == expected else "✗"
        print(f"Test {i}: {pan1} == {pan2} -> {actual} (expected {expected}) {status}")
    
    # Test Aadhar card normalization
    aadhar_test_cases = [
        ('1234-5678-9012', '1234-5678-9012', True),   # Same Aadhar should match
        ('1234-5678-9012', '1234-5678-9013', False),  # Different Aadhars should not match
        ('', '', True),                               # Empty strings should match
        (None, None, True),                          # None values should match
        ('1234-5678-9012', '', False),               # Different values should not match
    ]
    
    print("\nTesting Aadhar card comparison logic:")
    for i, (aadhar1, aadhar2, expected) in enumerate(aadhar_test_cases, 1):
        # Simulate the logic from get_user_by_aadhar_card
        if not aadhar1:
            result1 = None
        else:
            result1 = aadhar1.strip()
            
        if not aadhar2:
            result2 = None
        else:
            result2 = aadhar2.strip()
            
        actual = (result1 == result2)
        status = "✓" if actual == expected else "✗"
        print(f"Test {i}: {aadhar1} == {aadhar2} -> {actual} (expected {expected}) {status}")
    
    print("\nPAN and Aadhar validation logic test completed!")

if __name__ == "__main__":
    test_pan_aadhar_logic()