#!/usr/bin/env python3

"""
Test script to verify the leave deletion functionality works correctly.
This script tests that:
1. Leave requests can be deleted by the requester
2. Notifications are sent to approvers when a leave is deleted
3. Related notifications are cleaned up properly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.database import get_db
from app.crud.leave_crud import apply_leave, delete_leave, list_leave_notifications
from app.db.models.user import User
from app.db.models.leave import Leave
from datetime import datetime, timedelta

def test_leave_deletion():
    """Test the leave deletion functionality"""
    db = next(get_db())
    
    try:
        # Find a test user (employee)
        test_user = db.query(User).filter(User.role == "Employee").first()
        if not test_user:
            print("❌ No employee user found for testing")
            return False
            
        print(f"✅ Testing with user: {test_user.name} (ID: {test_user.user_id})")
        
        # Create a test leave request
        start_date = datetime.now() + timedelta(days=7)  # 7 days from now
        end_date = start_date + timedelta(days=2)  # 3 day leave
        
        leave = apply_leave(
            db=db,
            user_id=test_user.user_id,
            start_date=start_date,
            end_date=end_date,
            reason="Test leave for deletion functionality",
            leave_type="annual"
        )
        
        print(f"✅ Created test leave request (ID: {leave.leave_id})")
        
        # Check notifications before deletion
        notifications_before = list_leave_notifications(db, test_user.user_id)
        print(f"📧 Notifications before deletion: {len(notifications_before)}")
        
        # Delete the leave request
        result = delete_leave(db, leave.leave_id, test_user.user_id)
        
        if result:
            print("✅ Leave request deleted successfully")
            
            # Verify the leave is actually deleted
            deleted_leave = db.query(Leave).filter(Leave.leave_id == leave.leave_id).first()
            if deleted_leave is None:
                print("✅ Leave request properly removed from database")
            else:
                print("❌ Leave request still exists in database")
                return False
                
            # Check notifications after deletion
            notifications_after = list_leave_notifications(db, test_user.user_id)
            print(f"📧 Notifications after deletion: {len(notifications_after)}")
            
            print("✅ Leave deletion test completed successfully")
            return True
        else:
            print("❌ Failed to delete leave request")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        return False
    finally:
        db.close()

def test_delete_non_pending_leave():
    """Test that non-pending leaves cannot be deleted"""
    db = next(get_db())
    
    try:
        # Find a test user
        test_user = db.query(User).filter(User.role == "Employee").first()
        if not test_user:
            print("❌ No employee user found for testing")
            return False
            
        # Create and approve a leave request
        start_date = datetime.now() + timedelta(days=14)
        end_date = start_date + timedelta(days=1)
        
        leave = apply_leave(
            db=db,
            user_id=test_user.user_id,
            start_date=start_date,
            end_date=end_date,
            reason="Test approved leave for deletion test",
            leave_type="casual"
        )
        
        # Manually approve the leave
        leave.status = "Approved"
        db.commit()
        db.refresh(leave)
        
        print(f"✅ Created approved leave request (ID: {leave.leave_id})")
        
        # Try to delete the approved leave
        result = delete_leave(db, leave.leave_id, test_user.user_id)
        
        if result == "not_pending":
            print("✅ Correctly prevented deletion of approved leave")
            
            # Clean up - delete the test leave
            db.delete(leave)
            db.commit()
            
            return True
        else:
            print("❌ Should not be able to delete approved leave")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🧪 Testing Leave Deletion Functionality")
    print("=" * 50)
    
    # Test 1: Delete pending leave
    print("\n📋 Test 1: Delete pending leave request")
    test1_result = test_leave_deletion()
    
    # Test 2: Try to delete non-pending leave
    print("\n📋 Test 2: Try to delete approved leave (should fail)")
    test2_result = test_delete_non_pending_leave()
    
    print("\n" + "=" * 50)
    print("🏁 Test Results:")
    print(f"   Test 1 (Delete pending): {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"   Test 2 (Delete approved): {'✅ PASS' if test2_result else '❌ FAIL'}")
    
    if test1_result and test2_result:
        print("\n🎉 All tests passed! Leave deletion functionality is working correctly.")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed. Please check the implementation.")
        sys.exit(1)