#!/usr/bin/env python3
"""
Quick test to verify the late arrival fix is working
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_dashboard():
    """Test the admin dashboard response"""
    
    print("🔍 Testing Admin Dashboard After Fix")
    print("=" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/dashboard/admin", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            print("✅ Dashboard data received")
            print(f"Late Arrivals Count: {data.get('lateArrivals', 'N/A')}")
            
            recent_activities = data.get('recentActivities', [])
            print(f"\nRecent Activities ({len(recent_activities)} items):")
            
            for i, activity in enumerate(recent_activities, 1):
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
                    
                    # Status icons
                    status_icon = {
                        'early': '🌅',
                        'on-time': '✅', 
                        'late': '⏰'
                    }.get(status, '❓')
                    
                    print(f"  {i}. {status_icon} {user} - {time_display} ({status})")
                    
                    # Check if late arrivals are properly detected
                    if time_display.startswith('11:') and status != 'late':
                        print(f"     ⚠️  ISSUE: {time_display} should be LATE but shows as {status}")
                    elif time_display.startswith('11:') and status == 'late':
                        print(f"     ✅ CORRECT: {time_display} properly marked as LATE")
                        
        else:
            print(f"❌ Status: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_dashboard()