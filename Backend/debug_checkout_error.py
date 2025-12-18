#!/usr/bin/env python3
"""
Debug script to identify the 500 error in check-out endpoint
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models.attendance import Attendance
from app.db.models.user import User
from datetime import datetime
import traceback

def debug_checkout_issue():
    """Debug the check-out functionality"""
    print("🔍 Debugging check-out issue...")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Check if there are any users
        users = db.query(User).filter(User.is_active == True).all()
        print(f"📊 Found {len(users)} active users")
        
        if not users:
            print("❌ No active users found!")
            return
            
        # Check today's attendance records
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_attendances = db.query(Attendance).filter(
            Attendance.check_in >= today_start,
            Attendance.check_out.is_(None)
        ).all()
        
        print(f"📅 Found {len(today_attendances)} unchecked-out attendance records today")
        
        for attendance in today_attendances:
            user = db.query(User).filter(User.user_id == attendance.user_id).first()
            print(f"  - User {attendance.user_id} ({user.name if user else 'Unknown'}) checked in at {attendance.check_in}")
        
        # Test the check-out logic manually
        if today_attendances:
            test_attendance = today_attendances[0]
            print(f"\n🧪 Testing check-out logic for user {test_attendance.user_id}...")
            
            # Simulate check-out
            test_attendance.check_out = datetime.utcnow()
            test_attendance.work_summary = "Test summary"
            
            # Calculate hours
            if test_attendance.check_in and test_attendance.check_out:
                time_worked = test_attendance.check_out - test_attendance.check_in
                test_attendance.total_hours = round(time_worked.total_seconds() / 3600, 2)
                print(f"✅ Calculated work hours: {test_attendance.total_hours}")
            
            # Don't commit - just test
            print("✅ Check-out logic test passed")
            
        print("\n✅ Debug completed successfully")
        
    except Exception as e:
        print(f"❌ Error during debug: {e}")
        print(f"📋 Traceback: {traceback.format_exc()}")
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    debug_checkout_issue()