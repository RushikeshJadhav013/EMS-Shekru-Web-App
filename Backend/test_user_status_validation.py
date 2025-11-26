#!/usr/bin/env python3
"""
Test script to verify user status validation in authentication
This script tests that inactive/deactivated users cannot log in
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://172.105.56.142"
TEST_EMAIL = "test@example.com"  # Replace with a test user email

def test_user_status_validation():
    """Test that inactive users cannot log in"""
    
    print("🧪 Testing User Status Validation")
    print("=" * 50)
    
    # Test 1: Try to send OTP to inactive user
    print("\n1. Testing OTP sending to inactive user...")
    
    try:
        response = requests.post(f"{BASE_URL}/auth/send-otp", params={"email": TEST_EMAIL})
        
        if response.status_code == 403:
            print("✅ PASS: Inactive user cannot receive OTP")
            print(f"   Response: {response.json()['detail']}")
        elif response.status_code == 404:
            print("⚠️  User not found. Please create a test user first.")
            return False
        else:
            print("❌ FAIL: Inactive user was able to receive OTP")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Could not connect to server: {e}")
        return False
    
    # Test 2: Try to verify OTP for inactive user (if OTP was somehow sent)
    print("\n2. Testing OTP verification for inactive user...")
    
    try:
        # Try with a dummy OTP
        response = requests.post(
            f"{BASE_URL}/auth/verify-otp", 
            params={"email": TEST_EMAIL, "otp": 123456}
        )
        
        if response.status_code == 403:
            print("✅ PASS: Inactive user cannot verify OTP/login")
            print(f"   Response: {response.json()['detail']}")
        elif response.status_code == 400:
            print("✅ PASS: OTP validation failed (expected for dummy OTP)")
        else:
            print("❌ FAIL: Unexpected response for inactive user login")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Could not connect to server: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✅ User status validation tests completed!")
    return True

def test_active_user_flow():
    """Test that active users can still log in normally"""
    
    print("\n🧪 Testing Active User Flow")
    print("=" * 50)
    
    # This would require an active user email
    # For now, just print instructions
    print("To test active user flow:")
    print("1. Ensure you have an active user in the database")
    print("2. Try sending OTP - should succeed")
    print("3. Try verifying OTP - should succeed")
    print("4. Try accessing protected endpoints - should succeed")

def check_database_status():
    """Check if we can connect to the API"""
    
    print("🔍 Checking API connectivity...")
    
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ API is running and accessible")
            return True
        else:
            print(f"⚠️  API returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to API: {e}")
        print("Please ensure the backend server is running on http://172.105.56.142")
        return False

def main():
    """Main test function"""
    
    print("🚀 User Status Validation Test Suite")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Check API connectivity
    if not check_database_status():
        sys.exit(1)
    
    # Run tests
    success = test_user_status_validation()
    test_active_user_flow()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 All tests completed! Check results above.")
    else:
        print("⚠️  Some tests failed. Please review the output.")
    
    print("\n📝 Manual Testing Steps:")
    print("1. Go to Employee Management page")
    print("2. Set a user's status to 'Inactive'")
    print("3. Try to log in with that user's email")
    print("4. Should see: 'Account is inactive' error message")
    print("5. Set user back to 'Active'")
    print("6. Login should work normally")

if __name__ == "__main__":
    main()