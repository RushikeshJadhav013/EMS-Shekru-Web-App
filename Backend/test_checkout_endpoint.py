#!/usr/bin/env python3
"""
Test the check-out endpoint directly to identify the 500 error
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_db
from app.db.models.attendance import Attendance
from app.db.models.user import User
from datetime import datetime
import json

def test_checkout_endpoint():
    """Test the check-out endpoint directly"""
    print("🧪 Testing check-out endpoint...")
    
    client = TestClient(app)
    
    try:
        # Get database session
        db = next(get_db())
        
        # Find a user to test with
        user = db.query(User).filter(User.is_active == True).first()
        if not user:
            print("❌ No active users found!")
            return
            
        print(f"👤 Testing with user: {user.name} (ID: {user.user_id})")
        
        # Check if user has an active check-in today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        attendance = db.query(Attendance).filter(
            Attendance.user_id == user.user_id,
            Attendance.check_in >= today_start,
            Attendance.check_out.is_(None)
        ).first()
        
        if not attendance:
            print("📝 No active check-in found. Creating one for testing...")
            # Create a test check-in
            attendance = Attendance(
                user_id=user.user_id,
                check_in=datetime.utcnow(),
                gps_location="Test location",
                work_location="office"
            )
            db.add(attendance)
            db.commit()
            db.refresh(attendance)
            print(f"✅ Created test check-in: {attendance.attendance_id}")
        
        # Test the check-out endpoint
        payload = {
            "user_id": user.user_id,
            "gps_location": {
                "latitude": 19.0760,
                "longitude": 72.8777,
                "address": "Mumbai, India"
            },
            "work_summary": "Test work summary for debugging"
        }
        
        print("📤 Sending check-out request...")
        response = client.post("/attendance/check-out/json", json=payload)
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📋 Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✅ Check-out successful!")
        elif response.status_code == 500:
            print("❌ 500 Internal Server Error - checking logs...")
            # Try to get more details
            try:
                error_data = response.json()
                print(f"🔍 Error details: {error_data}")
            except:
                print("🔍 No JSON error details available")
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    test_checkout_endpoint()