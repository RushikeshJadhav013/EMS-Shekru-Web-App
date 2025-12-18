#!/usr/bin/env python3
"""
Debug script to check attendance records and help with check-out issues
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models.attendance import Attendance
from app.db.models.user import User
from datetime import datetime, timedelta
import traceback

def debug_attendance_records():
    """Debug attendance records to understand check-out issues"""
    print("🔍 Debugging attendance records...")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Check active users
        users = db.query(User).filter(User.is_active == True).all()
        print(f"👥 Found {len(users)} active users")
        
        # Check today's attendance records
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        print(f"📅 Checking attendance for today: {today_start.date()}")
        
        # Get all attendance records for today
        all_today_attendance = db.query(Attendance).filter(
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end
        ).all()
        
        print(f"📊 Total attendance records today: {len(all_today_attendance)}")
        
        # Check unchecked-out records
        unchecked_out = db.query(Attendance).filter(
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            Attendance.check_out.is_(None)
        ).all()
        
        print(f"🔓 Unchecked-out records today: {len(unchecked_out)}")
        
        if unchecked_out:
            print("\n📋 Unchecked-out attendance records:")
            for attendance in unchecked_out:
                user = db.query(User).filter(User.user_id == attendance.user_id).first()
                print(f"  - User ID: {attendance.user_id} ({user.name if user else 'Unknown'})")
                print(f"    Check-in: {attendance.check_in}")
                print(f"    Attendance ID: {attendance.attendance_id}")
                print(f"    Location: {attendance.gps_location}")
                print()
        
        # Check recent attendance records (last 3 days)
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        recent_attendance = db.query(Attendance).filter(
            Attendance.check_in >= three_days_ago
        ).order_by(Attendance.check_in.desc()).limit(10).all()
        
        print(f"📈 Recent attendance records (last 3 days, max 10):")
        for attendance in recent_attendance:
            user = db.query(User).filter(User.user_id == attendance.user_id).first()
            status = "✅ Complete" if attendance.check_out else "🔓 Pending checkout"
            print(f"  - {attendance.check_in.date()} | User: {user.name if user else 'Unknown'} | {status}")
        
        # Suggest solutions
        print("\n💡 Suggestions:")
        if len(unchecked_out) == 0:
            print("  1. No active check-ins found. User needs to check in first.")
            print("  2. Or create a test check-in for debugging.")
        else:
            print(f"  1. Found {len(unchecked_out)} users who can check out.")
            print("  2. Try check-out with one of the user IDs listed above.")
        
        # Offer to create a test check-in
        if len(unchecked_out) == 0 and users:
            test_user = users[0]
            print(f"\n🧪 Creating test check-in for user: {test_user.name} (ID: {test_user.user_id})")
            
            test_attendance = Attendance(
                user_id=test_user.user_id,
                check_in=datetime.utcnow(),
                gps_location="Test location for debugging",
                work_location="office"
            )
            db.add(test_attendance)
            db.commit()
            db.refresh(test_attendance)
            
            print(f"✅ Created test attendance record: {test_attendance.attendance_id}")
            print(f"   Now you can try checking out with user_id: {test_user.user_id}")
        
        print("\n✅ Debug completed successfully")
        
    except Exception as e:
        print(f"❌ Error during debug: {e}")
        print(f"📋 Traceback: {traceback.format_exc()}")
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    debug_attendance_records()