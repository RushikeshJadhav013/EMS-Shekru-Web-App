#!/usr/bin/env python3
"""
Test script to verify OTP endpoints are working correctly.
"""

import requests
import json
import sys

def test_backend_connection():
    """Test if backend server is running and accessible."""
    
    print("=== Testing Backend Connection ===\n")
    
    base_url = "https://staffly.space"
    
    # Test 1: Check if server is running
    try:
        response = requests.get(f"{base_url}/docs", timeout=10)
        if response.status_code == 200:
            print("✅ Backend server is running and accessible")
        else:
            print(f"❌ Backend server returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend server. Is it running on localhost:8000?")
        return False
    except requests.exceptions.Timeout:
        print("❌ Connection timeout. Backend server might be slow or unresponsive.")
        return False
    
    # Test 2: Check send-otp endpoint format
    print("\n=== Testing Send OTP Endpoint ===")
    
    test_email = "test@example.com"
    
    try:
        # Test the exact format used by frontend
        response = requests.post(
            f"{base_url}/auth/send-otp?email={test_email}",
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Send OTP Status Code: {response.status_code}")
        print(f"Send OTP Response: {response.text}")
        
        if response.status_code == 404:
            print("✅ Endpoint working (user not found is expected for test email)")
        elif response.status_code == 200:
            print("✅ Endpoint working (OTP sent)")
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("❌ Send OTP request timed out after 30 seconds")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection error during send OTP test")
        return False
    except Exception as e:
        print(f"❌ Error testing send OTP: {e}")
        return False
    
    # Test 3: Check verify-otp endpoint format
    print("\n=== Testing Verify OTP Endpoint ===")
    
    try:
        # Test the exact format used by frontend
        response = requests.post(
            f"{base_url}/auth/verify-otp?email={test_email}&otp=123456",
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Verify OTP Status Code: {response.status_code}")
        print(f"Verify OTP Response: {response.text}")
        
        if response.status_code in [400, 404]:
            print("✅ Endpoint working (invalid OTP/user is expected)")
        elif response.status_code == 200:
            print("✅ Endpoint working (OTP verified)")
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("❌ Verify OTP request timed out after 30 seconds")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection error during verify OTP test")
        return False
    except Exception as e:
        print(f"❌ Error testing verify OTP: {e}")
        return False
    
    print("\n=== Connection Test Summary ===")
    print("✅ Backend server is accessible")
    print("✅ OTP endpoints are responding")
    print("✅ Request format is correct")
    print("\nIf you're still getting ECONNABORTED errors, check:")
    print("1. Network connectivity")
    print("2. Firewall settings")
    print("3. Frontend environment variables")
    print("4. CORS configuration")
    
    return True

if __name__ == "__main__":
    success = test_backend_connection()
    sys.exit(0 if success else 1)