#!/usr/bin/env python3
"""
Debug script to test attendance API endpoint and identify the internal server error
"""

import sys
import os
import json
from datetime import datetime, date, timedelta

# Add the Backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_attendance_api():
    """Test the attendance API endpoint to identify the error"""
    
    try:
        from app.db.database import SessionLocal
        from app.db.models.user import User
        from app.db.models.attendance import Attendance
        from app.routes.attendance_routes import get_self_attendance, _prepare_attendance_payload
        
        print("🔧 Testing Attendance API...")
        
        # First, let's check if we have any users and attendance records
        db = SessionLocal()
        users = db.query(User).limit(5).all()
        
        if not users:
            print("❌ No users found in database")
            db.close()
            return False
        
        test_user = users[0]
        print(f"✅ Found user: {test_user.name} (ID: {test_user.user_id})")
        
        # Check if there are any attendance records
        attendance_records = db.query(Attendance).filter(
            Attendance.user_id == test_user.user_id
        ).limit(5).all()
        
        if not attendance_records:
            print("📝 No attendance records found. Creating a test record...")
            
            # Create a test attendance record
            test_attendance = Attendance(
                user_id=test_user.user_id,
                check_in=datetime.now() - timedelta(hours=8),
                check_out=datetime.now() - timedelta(hours=1),
                gps_location="Test Location",
                total_hours=7.0
            )
            db.add(test_attendance)
            db.commit()
            db.refresh(test_attendance)
            print(f"✅ Created test attendance record: ID {test_attendance.attendance_id}")
            attendance_records = [test_attendance]
        else:
            print(f"✅ Found {len(attendance_records)} attendance records")
        
        # Test the _prepare_attendance_payload function directly
        print("\n🔍 Testing _prepare_attendance_payload function...")
        try:
            test_record = attendance_records[0]
            print(f"Testing with attendance record: {test_record.attendance_id}")
            print(f"Check-in: {test_record.check_in}")
            print(f"Check-out: {test_record.check_out}")
            
            payload = _prepare_attendance_payload(test_record)
            print("✅ _prepare_attendance_payload worked successfully")
            print(f"Payload keys: {list(payload.keys())}")
            
        except Exception as payload_error:
            print(f"❌ _prepare_attendance_payload failed: {payload_error}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test the get_self_attendance function directly
        print("\n🔍 Testing get_self_attendance function...")
        try:
            result = get_self_attendance(test_user.user_id, db)
            print(f"✅ get_self_attendance worked: returned {len(result)} records")
            
        except Exception as endpoint_error:
            print(f"❌ get_self_attendance failed: {endpoint_error}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test Pydantic schema validation
        print("\n🔍 Testing AttendanceOut schema validation...")
        try:
            from app.schemas.attendance_schema import AttendanceOut
            
            # Test with the actual payload from the function
            for i, record_data in enumerate(result):
                print(f"Testing record {i+1} schema validation...")
                validated_record = AttendanceOut(**record_data)
                print(f"✅ Record {i+1} schema validation passed")
            
        except Exception as schema_error:
            print(f"❌ Schema validation failed: {schema_error}")
            import traceback
            traceback.print_exc()
            return False
        
        db.close()
        print("\n✅ All tests passed! The attendance API should be working.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Attendance API Debug Test")
    print("=" * 50)
    
    success = test_attendance_api()
    
    if success:
        print("\n✅ Debug test completed successfully!")
        print("💡 The attendance API logic appears to be working correctly.")
    else:
        print("\n❌ Debug test failed!")
        print("🔧 Please check the error messages above for details.")
    
    print("=" * 50)