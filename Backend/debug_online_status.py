#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.routes.attendance_routes import router
from app.db.models.user import User
from app.enums import RoleEnum
import traceback

def test_online_status():
    db = SessionLocal()
    try:
        print("Testing online status endpoint...")
        
        # Create a mock admin user for testing
        class MockUser:
            def __init__(self):
                self.user_id = 1
                self.role = RoleEnum.ADMIN
        
        # Import the function directly
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from app.db.models.attendance import Attendance
        from app.db.models.online_status import OnlineStatus
        
        UTC_TZ = ZoneInfo("UTC")
        
        # Get today's date in UTC
        today_start = datetime.now(UTC_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Get all attendance records for today that haven't checked out
        today_attendances = db.query(Attendance).filter(
            Attendance.check_in >= today_start,
            Attendance.check_in < today_end,
            Attendance.check_out.is_(None)  # Only checked-in users
        ).all()
        
        print(f"Found {len(today_attendances)} active attendances today")
        
        status_map = {}
        
        for attendance in today_attendances:
            # Get the latest status log for this attendance
            latest_status = db.query(OnlineStatus).filter(
                OnlineStatus.attendance_id == attendance.attendance_id
            ).order_by(OnlineStatus.timestamp.desc()).first()
            
            # Default to online if no status logs (just checked in)
            is_online = True if not latest_status else latest_status.is_online
            
            status_map[attendance.user_id] = {
                "is_online": is_online,
                "attendance_id": attendance.attendance_id,
                "check_in": attendance.check_in.isoformat(),
                "last_status_change": latest_status.timestamp.isoformat() if latest_status else attendance.check_in.isoformat()
            }
        
        print("Success!")
        print(f"Result: {status_map}")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Full traceback:")
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_online_status()