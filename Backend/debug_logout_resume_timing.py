#!/usr/bin/env python3
"""
Debug script to test logout/resume timing calculations
This helps identify timezone and calculation issues
"""

import requests
import json
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Test configuration
BASE_URL = "https://staffly.space"
TEST_EMAIL = "employee@company.com"
TEST_OTP = 123456

UTC_TZ = ZoneInfo("UTC")
IST_TZ = ZoneInfo("Asia/Kolkata")

def debug_logout_resume_timing():
    """Debug the logout/resume timing calculations"""
    
    print("🔍 Debugging Logout/Resume Timing Issues")
    print("=" * 60)
    
    # Step 1: Login and get token
    print("1. Logging in...")
    login_response = requests.post(f"{BASE_URL}/auth/verify-otp", json={
        "email": TEST_EMAIL,
        "otp": TEST_OTP
    })
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.text}")
        return False
    
    login_data = login_response.json()
    token = login_data["access_token"]
    user_id = int(login_data["user_id"])
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"✅ Login successful for user {user_id}")
    
    # Step 2: Check current user online status
    print("\n2. Checking current user online status...")
    status_response = requests.get(f"{BASE_URL}/attendance/user-online-status/{user_id}", headers=headers)
    
    if status_response.status_code == 200:
        status_data = status_response.json()
        print(f"📊 Current status: {json.dumps(status_data, indent=2)}")
        
        if status_data.get('is_checked_in'):
            attendance_id = status_data['attendance_id']
            
            # Step 3: Get working hours calculation
            print(f"\n3. Getting working hours for attendance {attendance_id}...")
            hours_response = requests.get(f"{BASE_URL}/attendance/working-hours/{attendance_id}", headers=headers)
            
            if hours_response.status_code == 200:
                hours_data = hours_response.json()
                print(f"📊 Working hours data: {json.dumps(hours_data, indent=2)}")
                
                # Analyze the timing
                check_in_time = datetime.fromisoformat(hours_data['check_in'].replace('Z', '+00:00'))
                current_time = datetime.now(UTC_TZ)
                
                print(f"\n🕐 Timing Analysis:")
                print(f"   Check-in time (UTC): {check_in_time}")
                print(f"   Check-in time (IST): {check_in_time.astimezone(IST_TZ)}")
                print(f"   Current time (UTC): {current_time}")
                print(f"   Current time (IST): {current_time.astimezone(IST_TZ)}")
                
                total_elapsed = (current_time - check_in_time).total_seconds()
                backend_online = hours_data['total_seconds']
                backend_offline = hours_data.get('total_offline_seconds', 0)
                
                print(f"\n📈 Time Calculations:")
                print(f"   Total elapsed since check-in: {total_elapsed:.0f}s ({total_elapsed/3600:.2f}h)")
                print(f"   Backend online time: {backend_online}s ({backend_online/3600:.2f}h)")
                print(f"   Backend offline time: {backend_offline}s ({backend_offline/3600:.2f}h)")
                print(f"   Sum (online + offline): {backend_online + backend_offline}s ({(backend_online + backend_offline)/3600:.2f}h)")
                
                # Check for discrepancies
                time_diff = abs(total_elapsed - (backend_online + backend_offline))
                if time_diff > 60:  # More than 1 minute difference
                    print(f"⚠️  WARNING: Time discrepancy of {time_diff:.0f}s detected!")
                    print(f"   This could indicate timezone or calculation issues")
                else:
                    print(f"✅ Time calculations look consistent (diff: {time_diff:.0f}s)")
                
                # Check if the 6-hour issue is present
                if backend_online > total_elapsed + 3600:  # More than 1 hour over expected
                    hours_over = (backend_online - total_elapsed) / 3600
                    print(f"🚨 ISSUE DETECTED: Backend reports {hours_over:.1f} hours more than expected!")
                    print(f"   This could be the 6-hour issue you're experiencing")
                    
                    # Check if it's exactly 5.5 hours (IST offset)
                    if abs(hours_over - 5.5) < 0.1:
                        print(f"💡 This looks like an IST timezone offset issue (UTC+5:30)")
                
            else:
                print(f"❌ Failed to get working hours: {hours_response.text}")
        else:
            print("ℹ️  User is not currently checked in")
    else:
        print(f"❌ Failed to get user status: {status_response.text}")
    
    # Step 4: Test logout/resume cycle
    print(f"\n4. Testing logout/resume cycle...")
    
    # Record time before logout
    logout_time = datetime.now(UTC_TZ)
    print(f"   Logout time: {logout_time} (UTC)")
    print(f"   Logout time: {logout_time.astimezone(IST_TZ)} (IST)")
    
    # Logout
    logout_response = requests.post(f"{BASE_URL}/attendance/logout", 
        headers=headers,
        json={
            "user_id": user_id,
            "logout_timestamp": logout_time.isoformat()
        }
    )
    
    if logout_response.status_code == 200:
        print(f"✅ Logout successful")
        
        # Wait a few seconds
        print("   Waiting 3 seconds...")
        time.sleep(3)
        
        # Login again
        login_time = datetime.now(UTC_TZ)
        print(f"   Login time: {login_time} (UTC)")
        print(f"   Login time: {login_time.astimezone(IST_TZ)} (IST)")
        
        # Get new token
        login_response2 = requests.post(f"{BASE_URL}/auth/verify-otp", json={
            "email": TEST_EMAIL,
            "otp": TEST_OTP
        })
        
        if login_response2.status_code == 200:
            token2 = login_response2.json()["access_token"]
            headers2 = {"Authorization": f"Bearer {token2}"}
            
            # Call resume
            resume_response = requests.post(f"{BASE_URL}/attendance/login-resume",
                headers=headers2,
                json={
                    "user_id": user_id,
                    "login_timestamp": login_time.isoformat()
                }
            )
            
            if resume_response.status_code == 200:
                print(f"✅ Resume successful")
                
                # Check status again
                status_response2 = requests.get(f"{BASE_URL}/attendance/user-online-status/{user_id}", headers=headers2)
                if status_response2.status_code == 200:
                    status_data2 = status_response2.json()
                    last_change = datetime.fromisoformat(status_data2['last_status_change'].replace('Z', '+00:00'))
                    
                    print(f"\n📊 After resume:")
                    print(f"   Last status change: {last_change} (UTC)")
                    print(f"   Last status change: {last_change.astimezone(IST_TZ)} (IST)")
                    print(f"   Expected logout time: {logout_time} (UTC)")
                    print(f"   Time difference: {abs((last_change - logout_time).total_seconds()):.0f}s")
                    
            else:
                print(f"❌ Resume failed: {resume_response.text}")
        else:
            print(f"❌ Second login failed: {login_response2.text}")
    else:
        print(f"❌ Logout failed: {logout_response.text}")

if __name__ == "__main__":
    debug_logout_resume_timing()