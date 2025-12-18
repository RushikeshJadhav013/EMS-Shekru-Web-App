#!/usr/bin/env python3
"""
Simple test to verify check-out endpoint works
"""

import requests
import json

def test_checkout():
    """Test the check-out endpoint"""
    url = "https://staffly.space/attendance/check-out/json"
    
    # Test payload
    payload = {
        "user_id": 1,
        "gps_location": {
            "latitude": 19.0760,
            "longitude": 72.8777,
            "address": "Mumbai, India"
        },
        "work_summary": "Completed daily tasks and project work"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print("🧪 Testing check-out endpoint...")
        response = requests.post(url, json=payload, headers=headers)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Check-out successful!")
            data = response.json()
            print(f"📋 Response: {json.dumps(data, indent=2)}")
        elif response.status_code == 400:
            print("⚠️ 400 Bad Request")
            print(f"📋 Error: {response.text}")
        elif response.status_code == 500:
            print("❌ 500 Internal Server Error")
            print(f"📋 Error: {response.text}")
        else:
            print(f"⚠️ Unexpected status: {response.status_code}")
            print(f"📋 Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Is the backend server running?")
    except Exception as e:
        print(f"❌ Test error: {e}")

if __name__ == "__main__":
    test_checkout()