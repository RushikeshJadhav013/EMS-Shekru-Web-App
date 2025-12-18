#!/usr/bin/env python3
"""
Test script to verify logout pause/resume functionality works correctly.
This tests that logout records offline time and login resumes online time properly.
"""

import requests
import json
import time
from datetime import datetime, timedelta

# Test configuration
BASE_URL = "https://staffly.space"
TEST_EMAIL = "employee@company.com"
TEST_OTP = 123456  # Default OTP for testing

def test_logout_pause_resume():
    """Test the complete logout pause/resume flow"""
    
    print("🧪 Testing Logout Pause/Resume Functionality")
    print("=" * 50)
    
    # Step 1: Login
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
    
    # Step 2: Check-in
    print("2. Checking in...")
    checkin_response = requests.post(f"{BASE_URL}/attendance/check-in/json", 
        headers=headers,
        json={
            "user_id": user_id,
            "gps_location": {
                "latitude": 28.6139,
                "longitude": 77.2090,
                "address": "Test Location"
            }
        }
    )
    
    if checkin_response.status_code != 201:
        print(f"❌ Check-in failed: {checkin_response.text}")
        return False
    
    attendance_data = checkin_response.json()
    attendance_id = attendance_data["attendance_id"]
    print(f"✅ Check-in successful, attendance ID: {attendance_id}")
    
    # Step 3: Wait a bit to accumulate some online time
    print("3. Accumulating online time (5 seconds)...")
    time.sleep(5)
    
    # Step 4: Logout (pause)
    print("4. Logging out (pause)...")
    logout_response = requests.post(f"{BASE_URL}/attendance/logout",
        headers=headers,
        json={
            "user_id": user_id,
            "logout_timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )
    
    if logout_response.status_code != 200:
        print(f"❌ Logout failed: {logout_response.text}")
        return False
    
    print("✅ Logout successful - session paused")
    
    # Step 5: Wait to simulate offline time
    print("5. Simulating offline time (3 seconds)...")
    time.sleep(3)
    
    # Step 6: Login again (resume)
    print("6. Logging in again (resume)...")
    login_response2 = requests.post(f"{BASE_URL}/auth/verify-otp", json={
        "email": TEST_EMAIL,
        "otp": TEST_OTP
    })
    
    if login_response2.status_code != 200:
        print(f"❌ Second login failed: {login_response2.text}")
        return False
    
    login_data2 = login_response2.json()
    token2 = login_data2["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}
    
    # Call resume endpoint
    resume_response = requests.post(f"{BASE_URL}/attendance/login-resume",
        headers=headers2,
        json={
            "user_id": user_id,
            "login_timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )
    
    if resume_response.status_code != 200:
        print(f"❌ Resume failed: {resume_response.text}")
        return False
    
    print("✅ Login resume successful")
    
    # Step 7: Check working hours calculation
    print("7. Checking working hours calculation...")
    hours_response = requests.get(f"{BASE_URL}/attendance/working-hours/{attendance_id}",
        headers=headers2
    )
    
    if hours_response.status_code != 200:
        print(f"❌ Working hours check failed: {hours_response.text}")
        return False
    
    hours_data = hours_response.json()
    online_seconds = hours_data["total_seconds"]
    offline_seconds = hours_data.get("total_offline_seconds", 0)
    
    print(f"✅ Working hours calculated:")
    print(f"   - Online time: {online_seconds} seconds")
    print(f"   - Offline time: {offline_seconds} seconds")
    
    # Verify the logic
    if online_seconds >= 5 and offline_seconds >= 3:
        print("✅ Pause/Resume logic working correctly!")
        print(f"   - Online time includes time before logout: {online_seconds}s >= 5s ✓")
        print(f"   - Offline time includes logout period: {offline_seconds}s >= 3s ✓")
        return True
    else:
        print("❌ Pause/Resume logic not working correctly!")
        print(f"   - Expected online time >= 5s, got {online_seconds}s")
        print(f"   - Expected offline time >= 3s, got {offline_seconds}s")
        return False

if __name__ == "__main__":
    success = test_logout_pause_resume()
    if success:
        print("\n🎉 All tests passed! Logout pause/resume is working correctly.")
    else:
        print("\n💥 Tests failed! Check the implementation.")