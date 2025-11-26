#!/usr/bin/env python3
"""
Test script to verify the manager dashboard fix
Tests both the 500 error resolution and CORS headers in error responses
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_manager_dashboard():
    """Test the manager dashboard endpoint that was failing"""
    
    print("🧪 Testing Manager Dashboard Fix")
    print("=" * 50)
    print(f"Testing: {BASE_URL}/dashboard/manager")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Test without authentication (should get 401 but with CORS headers)
        print("1. Testing without authentication...")
        response = requests.get(f"{BASE_URL}/dashboard/manager", timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        print(f"   CORS Origin: {response.headers.get('Access-Control-Allow-Origin', 'Missing')}")
        print(f"   CORS Methods: {response.headers.get('Access-Control-Allow-Methods', 'Missing')}")
        print(f"   CORS Headers: {response.headers.get('Access-Control-Allow-Headers', 'Missing')}")
        
        if response.status_code == 401:
            print("   ✅ Expected 401 (authentication required)")
        elif response.status_code == 500:
            print("   ❌ Still getting 500 error - check server logs")
            print(f"   Response: {response.text}")
        else:
            print(f"   ⚠️  Unexpected status code: {response.status_code}")
        
        # Check CORS headers are present even in error responses
        cors_origin = response.headers.get('Access-Control-Allow-Origin')
        if cors_origin:
            print("   ✅ CORS headers present in error response")
        else:
            print("   ❌ CORS headers missing in error response")
        
        print()
        
        # Test with dummy token (should get 401 but with CORS headers)
        print("2. Testing with invalid token...")
        headers = {"Authorization": "Bearer invalid_token"}
        response = requests.get(f"{BASE_URL}/dashboard/manager", headers=headers, timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        print(f"   CORS Origin: {response.headers.get('Access-Control-Allow-Origin', 'Missing')}")
        
        if response.status_code in [401, 422]:
            print("   ✅ Expected authentication error")
        elif response.status_code == 500:
            print("   ❌ Still getting 500 error")
            print(f"   Response: {response.text}")
        
        print()
        
        # Test OPTIONS request (preflight)
        print("3. Testing OPTIONS request (CORS preflight)...")
        response = requests.options(f"{BASE_URL}/dashboard/manager", timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        print(f"   CORS Origin: {response.headers.get('Access-Control-Allow-Origin', 'Missing')}")
        print(f"   CORS Methods: {response.headers.get('Access-Control-Allow-Methods', 'Missing')}")
        
        if response.status_code == 200:
            print("   ✅ OPTIONS request successful")
        else:
            print(f"   ⚠️  OPTIONS request returned: {response.status_code}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Could not connect to server: {e}")
        print("Please ensure the backend server is running on http://localhost:8000")
        return False

def test_other_dashboard_endpoints():
    """Test other dashboard endpoints to ensure they work"""
    
    print("\n🔍 Testing Other Dashboard Endpoints")
    print("=" * 50)
    
    endpoints = [
        "/dashboard/admin",
        "/dashboard/hr", 
        "/dashboard/employee",
        "/dashboard/team-lead"
    ]
    
    for endpoint in endpoints:
        print(f"\nTesting: {endpoint}")
        
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            print(f"   Status: {response.status_code}")
            print(f"   CORS: {response.headers.get('Access-Control-Allow-Origin', 'Missing')}")
            
            if response.status_code in [200, 401, 422]:
                print("   ✅ Endpoint responding correctly")
            elif response.status_code == 500:
                print("   ❌ 500 error - may need similar fix")
            else:
                print(f"   ⚠️  Unexpected status: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def test_cors_in_errors():
    """Test that CORS headers are present in various error scenarios"""
    
    print("\n🌐 Testing CORS Headers in Error Responses")
    print("=" * 50)
    
    test_cases = [
        {"url": "/dashboard/nonexistent", "expected": 404, "description": "404 Not Found"},
        {"url": "/dashboard/manager", "expected": 401, "description": "401 Unauthorized"},
    ]
    
    for case in test_cases:
        print(f"\nTesting: {case['description']}")
        
        try:
            response = requests.get(f"{BASE_URL}{case['url']}", timeout=5)
            
            print(f"   Status: {response.status_code}")
            cors_origin = response.headers.get('Access-Control-Allow-Origin')
            cors_methods = response.headers.get('Access-Control-Allow-Methods')
            
            if cors_origin:
                print(f"   ✅ CORS Origin: {cors_origin}")
            else:
                print("   ❌ CORS Origin: Missing")
            
            if cors_methods:
                print(f"   ✅ CORS Methods: {cors_methods}")
            else:
                print("   ❌ CORS Methods: Missing")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def main():
    """Main test function"""
    
    print("🚀 Dashboard Manager Fix Verification")
    print("Testing the /dashboard/manager endpoint that was returning 500 errors")
    print()
    
    # Test basic connectivity
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Backend is running (Status: {response.status_code})")
    except:
        print("❌ Cannot connect to backend. Please ensure it's running on http://localhost:8000")
        return
    
    # Run tests
    success = test_manager_dashboard()
    test_other_dashboard_endpoints()
    test_cors_in_errors()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Dashboard manager fix verification completed!")
        print()
        print("Expected Results:")
        print("✅ No more 500 Internal Server Error")
        print("✅ CORS headers present in all responses (including errors)")
        print("✅ 401 Unauthorized (authentication required) instead of 500")
        print("✅ OPTIONS requests work for CORS preflight")
    else:
        print("⚠️  Some issues detected. Please check the output above.")
    
    print("\n📝 Next Steps:")
    print("1. If tests pass, try your frontend application")
    print("2. Login with a manager account to test the full flow")
    print("3. Check that the manager dashboard loads without CORS errors")
    print("4. Verify other dashboard endpoints work correctly")

if __name__ == "__main__":
    main()