#!/usr/bin/env python3
"""
Debug script for the working-hours endpoint 500 error.
"""

import sys
sys.path.append('.')

from app.db.database import get_db
from app.db.models.attendance import Attendance
from app.db.models.online_status import OnlineStatus
from app.db.models.user import User
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import traceback

UTC_TZ = ZoneInfo("UTC")

def debug_working_hours_endpoint():
    """Debug the working hours calculation for attendance ID 34."""
    
    db = next(get_db())
    attendance_id = 34
    
    print(f"=== Debugging Working Hours Endpoint for Attendance ID {attendance_id} ===\n")
    
    try:
        # Step 1: Check if attendance exists
        print("1. Checking attendance record...")
        attendance = db.query(Attendance).filter(
            Attendance.attendance_id == attendance_id
        ).first()
        
        if not attendance:
            print(f"❌ Attendance record {attendance_id} not found")
            return
        
        print(f"✅ Attendance found:")
        print(f"   - User ID: {attendance.user_id}")
        print(f"   - Check-in: {attendance.check_in}")
        print(f"   - Check-out: {attendance.check_out}")
        
        # Step 2: Check status logs
        print(f"\n2. Checking online status logs...")
        status_logs = db.query(OnlineStatus).filter(
            OnlineStatus.attendance_id == attendance_id
        ).order_by(OnlineStatus.timestamp.asc()).all()
        
        print(f"   Found {len(status_logs)} status logs:")
        for i, log in enumerate(status_logs, 1):
            status_text = "Online" if log.is_online else "Offline"
            print(f"   {i}. {log.timestamp} - {status_text} ({log.reason})")
        
        # Step 3: Calculate working hours (simulate the endpoint logic)
        print(f"\n3. Calculating working hours...")
        
        total_online_seconds = 0
        last_online_time = None
        current_status = True  # Assume online after check-in (default)
        
        # Helper function to ensure timezone consistency
        def ensure_utc_timezone(dt):
            if dt is None:
                return None
            if dt.tzinfo is None:
                # Assume naive datetime is in UTC
                return dt.replace(tzinfo=UTC_TZ)
            return dt.astimezone(UTC_TZ)
        
        # Start from check-in time
        check_in_time = ensure_utc_timezone(attendance.check_in)
        last_online_time = check_in_time
        
        print(f"   Check-in time: {check_in_time}")
        
        # If no status logs exist, user has been online since check-in
        if not status_logs:
            print("   No status logs - calculating full time as online")
            end_time = ensure_utc_timezone(attendance.check_out) if attendance.check_out else datetime.now(UTC_TZ)
            total_online_seconds = (end_time - check_in_time).total_seconds()
            print(f"   End time: {end_time}")
            print(f"   Total online seconds: {total_online_seconds}")
        else:
            print("   Processing status logs...")
            # Process status logs
            for log in status_logs:
                log_timestamp = ensure_utc_timezone(log.timestamp)
                
                if log.is_online:
                    # Going online
                    print(f"   Going online at {log_timestamp}")
                    last_online_time = log_timestamp
                    current_status = True
                else:
                    # Going offline - calculate time since last online
                    if last_online_time:
                        duration = (log_timestamp - last_online_time).total_seconds()
                        total_online_seconds += duration
                        print(f"   Going offline at {log_timestamp}, adding {duration} seconds")
                    current_status = False
                    last_online_time = None
            
            # If currently online, add time until now or checkout
            if current_status and last_online_time:
                end_time = ensure_utc_timezone(attendance.check_out) if attendance.check_out else datetime.now(UTC_TZ)
                duration = (end_time - last_online_time).total_seconds()
                total_online_seconds += duration
                print(f"   Currently online, adding {duration} seconds until {end_time}")
        
        # Convert to hours
        working_hours = total_online_seconds / 3600
        
        print(f"\n4. Final Results:")
        print(f"   Total online seconds: {int(total_online_seconds)}")
        print(f"   Working hours: {round(working_hours, 2)}")
        print(f"   Currently online: {current_status}")
        
        # Step 4: Test the actual response format
        print(f"\n5. Response format test:")
        response = {
            "attendance_id": attendance_id,
            "working_hours": round(working_hours, 2),
            "total_seconds": int(total_online_seconds),
            "is_currently_online": current_status,
            "check_in": attendance.check_in.isoformat(),
            "check_out": attendance.check_out.isoformat() if attendance.check_out else None
        }
        print(f"   Response: {response}")
        
        print(f"\n✅ Working hours calculation completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error occurred:")
        print(f"   Error: {str(e)}")
        print(f"   Type: {type(e).__name__}")
        print(f"\nFull traceback:")
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    debug_working_hours_endpoint()