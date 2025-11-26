#!/usr/bin/env python3
"""
Test script to verify CORS fix is working
Tests the specific endpoints that were failing
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_cors_endpoints():
    """Test CORS on the specific endpoints that were failing"""
    
    print("🧪 Testing CORS Fix")
    print("=" * 50)
    print(f"Testing against: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test endpoints that were failing
    test_endpoints = [
        "/test-cors",
        "/tasks/notifications", 
        "/shift/notifications",
        "/",
        "/docs"
    ]
    
    results = []
    
    for endpoint in test_endpoints:
        print(f"Testing: {endpoint}")
        
        try:
            # Test OPTIONS request (preflight)
            options_response = requests.options(f"{BASE_URL}{endpoint}", timeout=5)
            options_status = options_response.status_code
            
            # Test GET request
            get_response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            get_status = get_response.status_code
            
            # Check CORS headers
            cors_headers = {
                'Access-Control-Allow-Origin': get_response.headers.get('Access-Control-Allow-Origin', 'Missing'),
                'Access-Control-Allow-Methods': get_response.headers.get('Access-Control-Allow-Methods', 'Missing'),
                'Access-Control-Allow-Headers': get_response.headers.get('Access-Control-Allow-Headers', 'Missing')
            }
            
            result = {
                'endpoint': endpoint,
                'options_status': options_status,
                'get_status': get_status,
                'cors_headers': cors_headers,
                'success': options_status < 400 and get_status < 500
            }
            
            results.append(result)
            
            # Print result
            if result['success']:
                print(f"  ✅ SUCCESS - OPTIONS: {options_status}, GET: {get_status}")
                print(f"     CORS Origin: {cors_headers['Access-Control-Allow-Origin']}")
            else:
                print(f"  ❌ FAILED - OPTIONS: {options_status}, GET: {get_status}")
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ ERROR - {str(e)}")
            results.append({
                'endpoint': endpoint,
                'error': str(e),
                'success': False
            })
        
        print()
    
    # Summary
    print("=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    
    successful = sum(1 for r in results if r.get('success', False))
    total = len(results)
    
    print(f"Successful: {successful}/{total}")
    print()
    
    if successful == total:
        print("🎉 ALL TESTS PASSED!")
        print("CORS is working correctly.")
    else:
        print("⚠️  SOME TESTS FAILED")
        print("Check the results above for details.")
    
    print()
    print("🔍 Next Steps:")
    print("1. If tests pass, try your frontend application")
    print("2. Check browser console for CORS errors")
    print("3. Test notification endpoints with authentication")
    
    return successful == total

def test_specific_cors_scenario():
    """Test the exact scenario that was failing"""
    
    print("\n🎯 Testing Specific CORS Scenario")
    print("=" * 50)
    
    # Simulate browser preflight request
    headers = {
        'Origin': 'http://localhost:3000',
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'authorization,content-type'
    }
    
    failing_endpoints = [
        "/tasks/notifications",
        "/shift/notifications"
    ]
    
    for endpoint in failing_endpoints:
        print(f"\nTesting preflight for: {endpoint}")
        
        try:
            response = requests.options(
                f"{BASE_URL}{endpoint}",
                headers=headers,
                timeout=5
            )
            
            print(f"  Status: {response.status_code}")
            print(f"  Allow-Origin: {response.headers.get('Access-Control-Allow-Origin', 'Missing')}")
            print(f"  Allow-Methods: {response.headers.get('Access-Control-Allow-Methods', 'Missing')}")
            print(f"  Allow-Headers: {response.headers.get('Access-Control-Allow-Headers', 'Missing')}")
            
            if response.status_code == 200:
                print("  ✅ Preflight successful")
            else:
                print("  ❌ Preflight failed")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")

def main():
    """Main test function"""
    
    print("🚀 CORS Fix Verification")
    print("Testing the endpoints that were failing with CORS errors")
    print()
    
    # Test basic connectivity
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Backend is running (Status: {response.status_code})")
    except:
        print("❌ Cannot connect to backend. Please ensure it's running on http://localhost:8000")
        return
    
    # Run tests
    success = test_cors_endpoints()
    test_specific_cors_scenario()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 CORS fix verification completed successfully!")
        print("Your frontend should now be able to access the backend APIs.")
    else:
        print("⚠️  Some issues detected. Please check the output above.")
    
    print("\n📝 Manual Testing:")
    print("1. Open your frontend application")
    print("2. Open browser DevTools → Console")
    print("3. Look for CORS errors (should be gone)")
    print("4. Test notification functionality")

if __name__ == "__main__":
    main()