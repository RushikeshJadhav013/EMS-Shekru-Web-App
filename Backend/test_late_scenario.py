#!/usr/bin/env python3
"""
Test to simulate the late arrival scenario from the screenshot
"""

def test_late_logic():
    """Test the logic for the specific times shown in the screenshot"""
    
    print("🧪 Testing Late Arrival Logic for Screenshot Scenario")
    print("=" * 60)
    
    # Test cases based on the screenshot
    test_cases = [
        {
            "user": "Mahesh Chole",
            "check_in_time": "11:32",
            "expected": "late"
        },
        {
            "user": "Aditya bhiiyaa Garad", 
            "check_in_time": "11:02",
            "expected": "late"
        }
    ]
    
    # Office timing configuration (fallback)
    office_start_minutes = 9 * 60 + 30  # 9:30 AM = 570 minutes
    late_threshold_minutes = office_start_minutes + 15  # 9:45 AM = 585 minutes
    
    print(f"Office Configuration:")
    print(f"  Start Time: 9:30 AM ({office_start_minutes} minutes)")
    print(f"  Grace Period: 15 minutes")
    print(f"  Late Threshold: 9:45 AM ({late_threshold_minutes} minutes)")
    print()
    
    for i, case in enumerate(test_cases, 1):
        print(f"{i}. Testing {case['user']} - {case['check_in_time']}")
        
        # Parse check-in time
        time_parts = case['check_in_time'].split(':')
        check_in_hour = int(time_parts[0])
        check_in_minute = int(time_parts[1])
        checkin_total_minutes = check_in_hour * 60 + check_in_minute
        
        # Apply the corrected logic
        if checkin_total_minutes < office_start_minutes:
            actual_status = 'early'
        elif checkin_total_minutes <= late_threshold_minutes:
            actual_status = 'on-time'
        else:
            actual_status = 'late'
        
        print(f"   Check-in: {case['check_in_time']} = {checkin_total_minutes} minutes")
        print(f"   Expected: {case['expected']}")
        print(f"   Actual: {actual_status}")
        
        if actual_status == case['expected']:
            print("   ✅ CORRECT - Should show as LATE")
        else:
            print("   ❌ INCORRECT - Logic error!")
        
        print()
    
    print("🔍 ANALYSIS:")
    print("If users are checking in at 11:32 AM and 11:02 AM but showing as 'On Time',")
    print("this indicates one of the following issues:")
    print()
    print("1. 🕐 TIMEZONE ISSUE:")
    print("   - Times might be stored in UTC but displayed in local time")
    print("   - Backend logic uses UTC, frontend displays local time")
    print()
    print("2. 📊 DATA INCONSISTENCY:")
    print("   - Screenshot shows different data than current database")
    print("   - Multiple database environments (dev/prod)")
    print()
    print("3. 🔄 CACHING ISSUE:")
    print("   - Frontend showing cached/stale data")
    print("   - Backend changes not reflected in UI")
    print()
    print("4. ⚙️ CONFIGURATION ISSUE:")
    print("   - Office timing configuration overriding fallback logic")
    print("   - Department-specific timings causing confusion")
    print()
    print("💡 RECOMMENDED ACTIONS:")
    print("1. Check if office timings are configured in database")
    print("2. Verify timezone handling in both backend and frontend")
    print("3. Clear browser cache and refresh dashboard")
    print("4. Check if users belong to departments with custom timings")

if __name__ == "__main__":
    test_late_logic()