#!/usr/bin/env python3
"""
Test to check office timing configuration
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_office_timing_config():
    """Test if office timings are configured"""
    
    print("⏰ Testing Office Timing Configuration")
    print("=" * 50)
    
    # Try to get office timings (this might require auth)
    endpoints_to_try = [
        "/attendance/office-hours",
        "/admin/office-timings", 
        "/office-timings"
    ]
    
    for endpoint in endpoints_to_try:
        try:
            print(f"Trying endpoint: {endpoint}")
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Success! Found office timings:")
                
                if isinstance(data, list):
                    for timing in data:
                        dept = timing.get('department', 'Global')
                        start_time = timing.get('start_time', 'N/A')
                        grace = timing.get('check_in_grace_minutes', 0)
                        print(f"    {dept}: {start_time} + {grace}min grace")
                else:
                    print(f"    Data: {json.dumps(data, indent=2)}")
                    
                return True
                
            elif response.status_code == 401:
                print(f"  ❌ Authentication required")
            elif response.status_code == 404:
                print(f"  ❌ Endpoint not found")
            else:
                print(f"  ❌ Error: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        print()
    
    print("No office timing configuration found via API")
    return False

def test_dashboard_debug():
    """Get detailed dashboard info for debugging"""
    
    print("🔍 Dashboard Debug Information")
    print("=" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/dashboard/admin", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            print("Dashboard Response Analysis:")
            print(f"  Late Arrivals Count: {data.get('lateArrivals', 'N/A')}")
            print(f"  Present Today: {data.get('presentToday', 'N/A')}")
            
            activities = data.get('recentActivities', [])
            print(f"  Recent Activities: {len(activities)} items")
            
            # Analyze each activity
            for activity in activities:
                if activity.get('type') == 'check-in':
                    user = activity.get('user', 'Unknown')
                    time_str = activity.get('time', 'N/A')
                    status = activity.get('status', 'N/A')
                    
                    print(f"    {user}: {time_str} -> {status}")
                    
                    # Check if this matches the screenshot scenario
                    if '11:' in time_str and status == 'on-time':
                        print(f"      ⚠️  ISSUE DETECTED: Late check-in showing as on-time!")
                    elif '11:' in time_str and status == 'late':
                        print(f"      ✅ CORRECT: Late check-in properly detected!")
            
        else:
            print(f"❌ Dashboard request failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🚀 Office Timing Configuration Debug")
    print()
    
    # Test connectivity
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Backend is running (Status: {response.status_code})")
    except:
        print("❌ Cannot connect to backend")
        exit(1)
    
    print()
    
    # Run tests
    test_office_timing_config()
    test_dashboard_debug()
    
    print("=" * 50)
    print("🎯 NEXT STEPS:")
    print("1. If office timings are configured, check if they have very late start times")
    print("2. Verify timezone handling between backend and frontend")
    print("3. Check if the issue persists after clearing browser cache")
    print("4. Test with fresh attendance data to confirm the fix works")