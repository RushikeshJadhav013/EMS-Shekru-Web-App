#!/usr/bin/env python3
"""
Test script for task deadline warnings system
"""
import requests
import json
from datetime import datetime, date, timedelta

API_BASE_URL = "https://staffly.space"

def test_deadline_warnings():
    """Test the task deadline warnings endpoint"""
    
    # Test user ID (replace with actual user ID)
    user_id = 1
    
    try:
        # Test the deadline warnings endpoint
        response = requests.get(f"{API_BASE_URL}/tasks/deadline-warnings/{user_id}")
        
        if response.status_code == 200:
            data = response.json()
            warnings = data.get('warnings', [])
            
            print(f"✅ Deadline warnings endpoint working!")
            print(f"Found {len(warnings)} warnings for user {user_id}")
            
            for warning in warnings:
                print(f"  - Task: {warning['title']}")
                print(f"    Due: {warning['due_date']}")
                print(f"    Type: {warning['warning_type']}")
                print(f"    Message: {warning['message']}")
                print()
                
        else:
            print(f"❌ Deadline warnings endpoint failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing deadline warnings: {e}")

def test_checkout_with_deadline_reason():
    """Test checkout with task deadline reason"""
    
    # Test data
    checkout_data = {
        "user_id": 1,
        "gps_location": json.dumps({
            "latitude": 19.0760,
            "longitude": 72.8777,
            "accuracy": 10,
            "address": "Mumbai, India"
        }),
        "work_summary": "Completed development tasks and attended meetings",
        "task_deadline_reason": "Task delayed due to dependency on external API which was not available today"
    }
    
    try:
        # Test checkout with deadline reason
        response = requests.post(f"{API_BASE_URL}/attendance/check-out", data=checkout_data)
        
        if response.status_code == 200:
            print("✅ Checkout with deadline reason working!")
            data = response.json()
            print(f"Checkout successful for user {data.get('user_id')}")
            if data.get('taskDeadlineReason'):
                print(f"Deadline reason saved: {data['taskDeadlineReason']}")
        else:
            print(f"❌ Checkout failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing checkout: {e}")

if __name__ == "__main__":
    print("Testing Task Deadline Warning System")
    print("=" * 50)
    
    print("\n1. Testing deadline warnings endpoint...")
    test_deadline_warnings()
    
    print("\n2. Testing checkout with deadline reason...")
    test_checkout_with_deadline_reason()
    
    print("\n✅ Testing complete!")