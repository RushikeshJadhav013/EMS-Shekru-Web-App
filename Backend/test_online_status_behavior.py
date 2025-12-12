#!/usr/bin/env python3
"""
Test script to verify online status behavior during check-in/check-out operations.
This script tests that online status only changes during attendance operations,
not during login/logout.
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "https://staffly.space"
TEST_EMAIL = "employee@company.com"  # Change this to a valid test user email
TEST_OTP = 123456  # This will work in development environment

def test_online_status_behavior():
    """Test that online status only changes during check-in/check-out, not login/logout"""
    
    print("🧪 Testing Online Status Behavior")
    print("=" * 50)
    
    # Step 1: Login
    print("\n1. Logging in user...")
    login_response = login_user(TEST_EMAIL, TEST_OTP)
    if not login_response:
        print("❌ Login failed")
        return False
    
    token = login_response['access_token']
    user_id = login_response['user_id']
    print(f"✅ Login successful for user {user_id}")
    
    # Step 2: Check initial online status (should be offline if not checked in)
    print("\n2. Checking initial online status...")
    initial_status = get_user_online_status(user_id, token)
    print(f"📊 Initial status: {initial_status}")
    
    # Step 3: Perform check-in
    print("\n3. Performing check-in...")
    checkin_result = perform_checkin(user_id, token)
    if not checkin_result:
        print("❌ Check-in failed")
        return False
    
    attendance_id = checkin_result.get('attendance_id')
    print(f"✅ Check-in successful, attendance ID: {attendance_id}")
    
    # Step 4: Check online status after check-in (should be online)
    print("\n4. Checking online status after check-in...")
    status_after_checkin = get_user_online_status(user_id, token)
    print(f"📊 Status after check-in: {status_after_checkin}")
    
    # Step 5: Simulate logout and login again
    print("\n5. Simulating logout and login again...")
    # We don't actually logout, just get a new token to simulate fresh login
    new_login_response = login_user(TEST_EMAIL, TEST_OTP)
    new_token = new_login_response['access_token']
    
    # Step 6: Check online status after re-login (should be preserved)
    print("\n6. Checking online status after re-login...")
    status_after_relogin = get_user_online_status(user_id, new_token)
    print(f"📊 Status after re-login: {status_after_relogin}")
    
    # Step 7: Manually toggle status to offline
    print("\n7. Manually toggling status to offline...")
    toggle_result = toggle_online_status(attendance_id, False, "Testing offline status", new_token)
    if toggle_result:
        print("✅ Successfully toggled to offline")
    
    # Step 8: Check status after manual toggle
    print("\n8. Checking status after manual toggle...")
    status_after_toggle = get_user_online_status(user_id, new_token)
    print(f"📊 Status after manual toggle: {status_after_toggle}")
    
    # Step 9: Simulate another logout/login
    print("\n9. Simulating another logout/login...")
    final_login_response = login_user(TEST_EMAIL, TEST_OTP)
    final_token = final_login_response['access_token']
    
    # Step 10: Check final status (should still be offline)
    print("\n10. Checking final status after re-login...")
    final_status = get_user_online_status(user_id, final_token)
    print(f"📊 Final status: {final_status}")
    
    # Step 11: Perform check-out
    print("\n11. Performing check-out...")
    checkout_result = perform_checkout(user_id, final_token)
    if checkout_result:
        print("✅ Check-out successful")
    
    # Step 12: Check status after check-out (should be offline)
    print("\n12. Checking status after check-out...")
    status_after_checkout = get_user_online_status(user_id, final_token)
    print(f"📊 Status after check-out: {status_after_checkout}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 TEST SUMMARY")
    print("=" * 50)
    
    # Verify expected behavior
    success = True
    
    # Check that status is preserved across login/logout
    if status_after_checkin.get('is_online') != status_after_relogin.get('is_online'):
        print("❌ FAIL: Online status not preserved across login/logout")
        success = False
    else:
        print("✅ PASS: Online status preserved across login/logout")
    
    # Check that manual toggle works
    if status_after_toggle.get('is_online') != False:
        print("❌ FAIL: Manual toggle to offline didn't work")
        success = False
    else:
        print("✅ PASS: Manual toggle to offline works")
    
    # Check that status is still preserved after toggle
    if status_after_toggle.get('is_online') != final_status.get('is_online'):
        print("❌ FAIL: Toggled status not preserved across login/logout")
        success = False
    else:
        print("✅ PASS: Toggled status preserved across login/logout")
    
    # Check that check-out sets status to offline
    if status_after_checkout.get('is_online') != False:
        print("❌ FAIL: Check-out didn't set status to offline")
        success = False
    else:
        print("✅ PASS: Check-out sets status to offline")
    
    if success:
        print("\n🎉 ALL TESTS PASSED! Online status behavior is correct.")
    else:
        print("\n💥 SOME TESTS FAILED! Please check the implementation.")
    
    return success

def login_user(email, otp):
    """Login user and return response"""
    try:
        # Send OTP first
        otp_response = requests.post(f"{BASE_URL}/auth/send-otp", params={"email": email})
        if otp_response.status_code != 200:
            print(f"Failed to send OTP: {otp_response.text}")
            return None
        
        # Verify OTP
        verify_response = requests.post(f"{BASE_URL}/auth/verify-otp", params={"email": email, "otp": otp})
        if verify_response.status_code != 200:
            print(f"Failed to verify OTP: {verify_response.text}")
            return None
        
        return verify_response.json()
    except Exception as e:
        print(f"Login error: {e}")
        return None

def get_user_online_status(user_id, token):
    """Get user's current online status"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/attendance/user-online-status/{user_id}", headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to get online status: {response.text}")
            return {}
    except Exception as e:
        print(f"Error getting online status: {e}")
        return {}

def perform_checkin(user_id, token):
    """Perform check-in"""
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "user_id": user_id,
            "gps_location": {
                "latitude": 19.0760,
                "longitude": 72.8777,
                "accuracy": 10,
                "address": "Test Location, Mumbai"
            },
            "selfie": None,
            "location_data": {
                "latitude": 19.0760,
                "longitude": 72.8777,
                "accuracy": 10,
                "address": "Test Location, Mumbai"
            }
        }
        
        response = requests.post(f"{BASE_URL}/attendance/check-in/json", headers=headers, json=payload)
        if response.status_code in [200, 201]:
            return response.json()
        else:
            print(f"Check-in failed: {response.text}")
            return None
    except Exception as e:
        print(f"Check-in error: {e}")
        return None

def perform_checkout(user_id, token):
    """Perform check-out"""
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "user_id": user_id,
            "gps_location": {
                "latitude": 19.0760,
                "longitude": 72.8777,
                "accuracy": 10,
                "address": "Test Location, Mumbai"
            },
            "work_summary": "Completed testing online status behavior",
            "selfie": None,
            "location_data": {
                "latitude": 19.0760,
                "longitude": 72.8777,
                "accuracy": 10,
                "address": "Test Location, Mumbai"
            }
        }
        
        response = requests.post(f"{BASE_URL}/attendance/check-out/json", headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Check-out failed: {response.text}")
            return None
    except Exception as e:
        print(f"Check-out error: {e}")
        return None

def toggle_online_status(attendance_id, is_online, reason, token):
    """Toggle online status"""
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "attendance_id": attendance_id,
            "is_online": is_online,
            "reason": reason
        }
        
        response = requests.post(f"{BASE_URL}/attendance/online-status", headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Toggle status failed: {response.text}")
            return None
    except Exception as e:
        print(f"Toggle status error: {e}")
        return None

if __name__ == "__main__":
    print("🚀 Starting Online Status Behavior Test")
    print("Make sure the backend server is running on https://staffly.space")
    print("This test requires a valid user account with email: employee@company.com")
    print()
    
    input("Press Enter to continue...")
    
    success = test_online_status_behavior()
    
    if success:
        exit(0)
    else:
        exit(1)