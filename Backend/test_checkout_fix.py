#!/usr/bin/env python3
"""
Quick test script to verify the check-out endpoint works without work_summary
"""

import requests
import json

# Test the check-out JSON endpoint without work_summary
def test_checkout_without_summary():
    url = "https://staffly.space/attendance/check-out/json"
    
    # Test payload without work_summary
    payload = {
        "user_id": 1,
        "gps_location": {
            "latitude": 19.0760,
            "longitude": 72.8777,
            "address": "Mumbai, India"
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        # Add your auth token here if needed
        # "Authorization": "Bearer your_token_here"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Check-out without work_summary works!")
        elif response.status_code == 400:
            print("❌ Still getting 400 error")
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the backend is running.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Testing check-out endpoint without work_summary...")
    test_checkout_without_summary()