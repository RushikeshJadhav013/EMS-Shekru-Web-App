#!/usr/bin/env python3
"""
Debug script to test leave API endpoint and identify the internal server error
"""

import sys
import os
import json
from datetime import datetime, date

# Add the Backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_leave_api():
    """Test the leave API endpoint to identify the error"""
    
    try:
        from app.db.database import SessionLocal
        from app.db.models.user import User
        from app.enums import RoleEnum
        
        print("🔧 Testing Leave API components...")
        
        # First, let's check if we have any users in the database
        db = SessionLocal()
        users = db.query(User).limit(5).all()
        
        if not users:
            print("❌ No users found in database")
            db.close()
            return False
        else:
            test_user = users[0]
            print(f"✅ Found user: {test_user.name} (ID: {test_user.user_id})")
        
        # Test leave request data (use future dates - more than 24 hours ahead)
        from datetime import datetime, timedelta
        start_date = datetime.now() + timedelta(days=2)  # 2 days from now
        end_date = datetime.now() + timedelta(days=3)    # 3 days from now
        
        leave_data = {
            "employee_id": test_user.employee_id,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "reason": "Test leave request for debugging purposes",
            "leave_type": "annual"
        }
        
        print(f"📝 Testing leave request with data: {json.dumps(leave_data, indent=2)}")
        
        # Now let's try to understand the schema validation
        print("\n🔍 Testing schema validation...")
        try:
            from app.schemas.leave_schema import LeaveCreate
            
            # Test if the data validates against the schema
            leave_create = LeaveCreate(**leave_data)
            print("✅ Schema validation passed")
            print(f"Validated data: {leave_create.model_dump()}")
            
        except Exception as schema_error:
            print(f"❌ Schema validation failed: {schema_error}")
            return False
        
        # Test the CRUD function directly
        print("\n🔍 Testing CRUD function directly...")
        try:
            from app.crud.leave_crud import apply_leave
            from datetime import datetime
            
            db = SessionLocal()
            
            start_date = datetime.strptime(leave_data["start_date"], "%Y-%m-%d")
            end_date = datetime.strptime(leave_data["end_date"], "%Y-%m-%d")
            
            leave = apply_leave(
                db=db,
                user_id=test_user.user_id,
                start_date=start_date,
                end_date=end_date,
                reason=leave_data["reason"],
                leave_type=leave_data["leave_type"]
            )
            
            print(f"✅ CRUD function worked: Leave ID {leave.leave_id}")
            db.close()
            
        except Exception as crud_error:
            print(f"❌ CRUD function failed: {crud_error}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test the route handler logic
        print("\n🔍 Testing route handler logic...")
        try:
            from app.routes.leave_routes import request_leave
            from app.schemas.leave_schema import LeaveCreate
            
            # Create a mock user object
            class MockUser:
                def __init__(self, user_id):
                    self.user_id = user_id
            
            mock_user = MockUser(test_user.user_id)
            leave_create = LeaveCreate(**leave_data)
            
            db = SessionLocal()
            
            # This should work if the route logic is correct
            result = request_leave(leave_create, db, mock_user)
            print(f"✅ Route handler worked: {result}")
            db.close()
            
        except Exception as route_error:
            print(f"❌ Route handler failed: {route_error}")
            import traceback
            traceback.print_exc()
            return False
        
        print("\n✅ All tests passed! The issue might be with authentication or middleware.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Leave API Debug Test")
    print("=" * 50)
    
    success = test_leave_api()
    
    if success:
        print("\n✅ Debug test completed successfully!")
        print("💡 The leave API logic appears to be working correctly.")
        print("🔍 The issue might be:")
        print("  1. Authentication middleware")
        print("  2. Database connection issues")
        print("  3. Missing dependencies")
        print("  4. CORS or request parsing issues")
    else:
        print("\n❌ Debug test failed!")
        print("🔧 Please check the error messages above for details.")
    
    print("=" * 50)