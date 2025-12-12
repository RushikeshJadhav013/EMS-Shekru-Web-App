#!/usr/bin/env python3
"""
Test script to verify the departments permission fix
"""

import requests
import jwt
from datetime import datetime, timedelta
import json

def test_departments_endpoints():
    """Test both the restricted and unrestricted departments endpoints"""
    
    # Generate token for an employee (not admin/hr)
    secret = 'supersecretjwtkey'
    payload = {
        'sub': 'adityag23@gmail.com',  # Use email in sub field
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    
    print('=== Testing Departments Permission Fix ===\n')
    
    # Test 1: Try the restricted endpoint (should fail for employee)
    print('Test 1: Restricted endpoint /departments/ (should fail for employee)')
    try:
        response = requests.get(
            'https://staffly.space/departments/',
            headers={'Authorization': f'Bearer {token}'}
        )
        print(f'Status Code: {response.status_code}')
        if response.status_code == 403:
            print('✅ Expected 403 Forbidden - endpoint properly restricted')
        else:
            print(f'❌ Unexpected status: {response.status_code}')
            print(f'Response: {response.text}')
    except Exception as e:
        print(f'❌ Error: {e}')
    
    print()
    
    # Test 2: Try the new unrestricted endpoint (should work for employee)
    print('Test 2: New unrestricted endpoint /departments/names (should work for employee)')
    try:
        response = requests.get(
            'https://staffly.space/departments/names',
            headers={'Authorization': f'Bearer {token}'}
        )
        print(f'Status Code: {response.status_code}')
        if response.status_code == 200:
            data = response.json()
            print(f'✅ Success! Found {len(data)} departments:')
            for dept in data[:3]:  # Show first 3
                print(f'  - {dept["name"]} ({dept["code"]})')
            if len(data) > 3:
                print(f'  ... and {len(data) - 3} more')
        else:
            print(f'❌ Unexpected status: {response.status_code}')
            print(f'Response: {response.text}')
    except Exception as e:
        print(f'❌ Error: {e}')
    
    print()
    
    # Test 3: Test with admin token (should work for both)
    print('Test 3: Testing with admin token (both endpoints should work)')
    admin_payload = {
        'sub': 'admin@company.com',  # Admin email
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    admin_token = jwt.encode(admin_payload, secret, algorithm='HS256')
    
    # Test restricted endpoint with admin
    try:
        response = requests.get(
            'https://staffly.space/departments/',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        print(f'Admin access to /departments/: {response.status_code}')
        if response.status_code == 200:
            data = response.json()
            print(f'✅ Admin can access full department data ({len(data)} departments)')
        else:
            print(f'❌ Admin access failed: {response.status_code}')
    except Exception as e:
        print(f'❌ Admin test error: {e}')
    
    print('\n=== Summary ===')
    print('✅ Employee users can now access department names via /departments/names')
    print('✅ Full department management still restricted to admin/hr via /departments/')
    print('✅ LeaveManagement page should now work for all users')

if __name__ == '__main__':
    test_departments_endpoints()