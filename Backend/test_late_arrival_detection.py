#!/usr/bin/env python3
"""
Test script to debug late arrival detection in admin dashboard
This will help identify why late check-ins are showing as "on-time"
"""

import requests
import json
from datetime import datetime, time
import sys

BASE_URL = "http://localhost:8000"

def test_late_arrival_logic():
    """Test the late arrival detection logic"""
    
    print("🧪 Testing Late Arrival Detection Logic")
    print("=" * 60)
    
    # Test different scenarios
    test_cases = [
        {
            "description": "Check-in at 9:00 AM (should be on-time)",
            "check_in_hour": 9,
            "check_in_minute": 0,
            "office_start": "09:30",
            "grace_minutes": 15,
            "expected": "on-time"
        },
        {
            "description": "Check-in at 9:30 AM (should be on-time)",
            "check_in_hour": 9,
            "check_in_minute": 30,
            "office_start": "09:30",
            "grace_minutes": 15,
            "expected": "on-time"
        },
        {
            "description": "Check-in at 9:45 AM (should be on-time with grace)",
            "check_in_hour": 9,
            "check_in_minute": 45,
            "office_start": "09:30",
            "grace_minutes": 15,
            "expected": "on-time"
        },
        {
            "description": "Check-in at 9:46 AM (should be late)",
            "check_in_hour": 9,
            "check_in_minute": 46,
            "office_start": "09:30",
            "grace_minutes": 15,
            "expected": "late"
        },
        {
            "description": "Check-in at 10:00 AM (should be late)",
            "check_in_hour": 10,
            "check_in_minute": 0,
            "office_start": "09:30",
            "grace_minutes": 15,
            "expected": "late"
        },
        {
            "description": "Check-in at 10:30 AM (should be late)",
            "check_in_hour": 10,
            "check_in_minute": 30,
            "office_start": "09:30",
            "grace_minutes": 15,
            "expected": "late"
        }
    ]
    
    print("Testing logic with different scenarios:")
    print()
    
    for i, case in enumerate(test_cases, 1):
        print(f"{i}. {case['description']}")
        
        # Parse office start time
        start_parts = case['office_start'].split(':')
        start_hour = int(start_parts[0])
        start_minute = int(start_parts[1])
        grace_minutes = case['grace_minutes']
        
        # Calculate threshold (same logic as in dashboard)
        start_total_minutes = start_hour * 60 + start_minute + grace_minutes
        checkin_total_minutes = case['check_in_hour'] * 60 + case['check_in_minute']
        
        # Determine status
        actual_status = 'on-time' if checkin_total_minutes <= start_total_minutes else 'late'
        
        print(f"   Office Start: {case['office_start']} + {grace_minutes} min grace = {start_total_minutes} minutes")
        print(f"   Check-in: {case['check_in_hour']:02d}:{case['check_in_minute']:02d} = {checkin_total_minutes} minutes")
        print(f"   Expected: {case['expected']}")
        print(f"   Actual: {actual_status}")
        
        if actual_status == case['expected']:
            print("   ✅ CORRECT")
        else:
            print("   ❌ INCORRECT - Logic error detected!")
        
        print()
    
    return True

def test_admin_dashboard_response():
    """Test the actual admin dashboard response"""
    
    print("🔍 Testing Admin Dashboard Response")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/dashboard/admin", timeout=10)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print("✅ Dashboard data received successfully")
            print()
            print("Summary Statistics:")
            print(f"  Total Employees: {data.get('totalEmployees', 'N/A')}")
            print(f"  Present Today: {data.get('presentToday', 'N/A')}")
            print(f"  Late Arrivals: {data.get('lateArrivals', 'N/A')}")
            print()
            
            recent_activities = data.get('recentActivities', [])
            print(f"Recent Activities ({len(recent_activities)} items):")
            
            if recent_activities:
                for i, activity in enumerate(recent_activities[:10], 1):  # Show first 10
                    if activity.get('type') == 'check-in':
                        time_str = activity.get('time', 'N/A')
                        status = activity.get('status', 'N/A')
                        user = activity.get('user', 'N/A')
                        
                        # Parse time to show just the time part
                        try:
                            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                            time_display = dt.strftime('%H:%M:%S')
                        except:
                            time_display = time_str
                        
                        status_icon = "✅" if status == "on-time" else "⏰" if status == "late" else "❓"
                        print(f"  {i:2d}. {status_icon} {user} - {time_display} ({status})")
            else:
                print("  No recent activities found")
            
            print()
            
            # Check for potential issues
            late_count = data.get('lateArrivals', 0)
            late_in_activities = sum(1 for act in recent_activities 
                                   if act.get('type') == 'check-in' and act.get('status') == 'late')
            
            print("Consistency Check:")
            print(f"  Late Arrivals (summary): {late_count}")
            print(f"  Late in Recent Activities: {late_in_activities}")
            
            if late_count > 0 and late_in_activities == 0:
                print("  ⚠️  INCONSISTENCY: Summary shows late arrivals but activities show all on-time")
            elif late_count == 0 and late_in_activities > 0:
                print("  ⚠️  INCONSISTENCY: Activities show late arrivals but summary shows none")
            else:
                print("  ✅ Summary and activities are consistent")
                
        elif response.status_code == 401:
            print("❌ Authentication required - cannot test without login")
            print("This is expected if no authentication token is provided")
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Could not connect to server: {e}")
        return False
    
    return True

def test_office_timings():
    """Test office timings configuration"""
    
    print("⏰ Testing Office Timings Configuration")
    print("=" * 60)
    
    try:
        # This endpoint might require authentication
        response = requests.get(f"{BASE_URL}/attendance/office-hours", timeout=10)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            timings = response.json()
            print("✅ Office timings retrieved successfully")
            print()
            
            if timings:
                for timing in timings:
                    dept = timing.get('department') or 'Global'
                    start_time = timing.get('start_time', 'N/A')
                    grace = timing.get('check_in_grace_minutes', 0)
                    
                    print(f"  {dept}:")
                    print(f"    Start Time: {start_time}")
                    print(f"    Grace Period: {grace} minutes")
                    print(f"    Late Threshold: {start_time} + {grace} min")
                    print()
            else:
                print("  No office timings configured - using defaults")
                print("  Default: 9:30 AM + 15 min grace = 9:45 AM threshold")
                
        elif response.status_code == 401:
            print("❌ Authentication required for office timings")
        else:
            print(f"❌ Could not retrieve office timings: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing office timings: {e}")

def main():
    """Main test function"""
    
    print("🚀 Late Arrival Detection Debug Tool")
    print("Investigating why late check-ins show as 'on-time' in admin dashboard")
    print()
    
    # Test basic connectivity
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Backend is running (Status: {response.status_code})")
    except:
        print("❌ Cannot connect to backend. Please ensure it's running on http://localhost:8000")
        return
    
    print()
    
    # Run tests
    test_late_arrival_logic()
    test_admin_dashboard_response()
    test_office_timings()
    
    print("=" * 60)
    print("🔍 DEBUGGING CHECKLIST:")
    print()
    print("1. ✅ Logic Test: Check if the time calculation logic is correct")
    print("2. 🔍 Dashboard Response: Check actual API response data")
    print("3. ⏰ Office Timings: Verify office timing configuration")
    print()
    print("📝 COMMON ISSUES:")
    print("• Timezone differences (UTC vs local time)")
    print("• Office timing configuration not set up")
    print("• Grace period calculation errors")
    print("• Database time format inconsistencies")
    print()
    print("💡 NEXT STEPS:")
    print("1. Check if office timings are properly configured")
    print("2. Verify timezone handling in check-in times")
    print("3. Test with actual late check-in data")
    print("4. Compare summary stats with activity details")

if __name__ == "__main__":
    main()