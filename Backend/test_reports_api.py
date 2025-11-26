"""
Test script to verify reports API endpoints work correctly
"""
import requests

BASE_URL = "http://172.105.56.142"

# Test without authentication first
def test_reports():
    print("Testing Reports API Endpoints...")
    print("=" * 60)
    
    # Test employee performance
    print("\n1. Testing /reports/employee-performance")
    try:
        response = requests.get(
            f"{BASE_URL}/reports/employee-performance",
            params={"month": 10, "year": 2025}
        )
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Success! Found {len(data.get('employees', []))} employees")
        elif response.status_code == 401:
            print("   ⚠ Authentication required (expected)")
        else:
            print(f"   ✗ Error: {response.text[:200]}")
    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")
    
    # Test department metrics
    print("\n2. Testing /reports/department-metrics")
    try:
        response = requests.get(
            f"{BASE_URL}/reports/department-metrics",
            params={"month": 10, "year": 2025}
        )
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Success! Found {len(data.get('departments', []))} departments")
        elif response.status_code == 401:
            print("   ⚠ Authentication required (expected)")
        else:
            print(f"   ✗ Error: {response.text[:200]}")
    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")
    
    # Test executive summary
    print("\n3. Testing /reports/executive-summary")
    try:
        response = requests.get(
            f"{BASE_URL}/reports/executive-summary",
            params={"month": 10, "year": 2025}
        )
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Success! Top performer: {data.get('topPerformer', {}).get('name', 'N/A')}")
        elif response.status_code == 401:
            print("   ⚠ Authentication required (expected)")
        else:
            print(f"   ✗ Error: {response.text[:200]}")
    except Exception as e:
        print(f"   ✗ Exception: {str(e)}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("\nNote: If you see 401 errors, that's expected - authentication is required.")
    print("If you see 500 errors, there's still a bug in the backend code.")
    print("\nTo test with authentication, add your token to the script.")

if __name__ == "__main__":
    test_reports()
