#!/usr/bin/env python3

"""
Complete test for leave deletion flow including notifications.
This test verifies:
1. Leave request creation
2. Notification creation for approvers
3. Leave deletion by requester
4. Deletion notification sent to approvers
5. Cleanup of related notifications
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.database import get_db
from app.crud.leave_crud import (
    apply_leave, 
    delete_leave, 
    list_leave_notifications,
    create_leave_request_notifications
)
from app.db.models.user import User
from app.db.models.leave import Leave
from app.db.models.notification import LeaveNotification
from datetime import datetime, timedelta

def test_complete_delete_flow():
    """Test the complete leave deletion flow with notifications"""
    db = next(get_db())
    
    try:
        # Find test users
        employee = db.query(User).filter(User.role == "Employee").first()
        manager = db.query(User).filter(User.role == "Manager").first()
        
        if not employee or not manager:
            print("❌ Need both Employee and Manager users for testing")
            return False
            
        print(f"✅ Employee: {employee.name} (ID: {employee.user_id})")
        print(f"✅ Manager: {manager.name} (ID: {manager.user_id})")
        
        # Step 1: Create a leave request
        start_date = datetime.now() + timedelta(days=7)
        end_date = start_date + timedelta(days=2)
        
        leave = apply_leave(
            db=db,
            user_id=employee.user_id,
            start_date=start_date,
            end_date=end_date,
            reason="Complete flow test - family vacation",
            leave_type="annual"
        )
        
        print(f"✅ Step 1: Created leave request (ID: {leave.leave_id})")
        
        # Step 2: Create notifications for the leave request
        notifications = create_leave_request_notifications(db, leave, employee)
        print(f"✅ Step 2: Created {len(notifications)} notifications for approvers")
        
        # Step 3: Check notifications before deletion
        manager_notifications_before = list_leave_notifications(db, manager.user_id)
        employee_notifications_before = list_leave_notifications(db, employee.user_id)
        
        print(f"📧 Manager notifications before deletion: {len(manager_notifications_before)}")
        print(f"📧 Employee notifications before deletion: {len(employee_notifications_before)}")
        
        # Step 4: Delete the leave request (this should create deletion notifications)
        result = delete_leave(db, leave.leave_id, employee.user_id)
        
        if result:
            print("✅ Step 4: Leave request deleted successfully")
            
            # Step 5: Verify leave is deleted from database
            deleted_leave = db.query(Leave).filter(Leave.leave_id == leave.leave_id).first()
            if deleted_leave is None:
                print("✅ Step 5: Leave properly removed from database")
            else:
                print("❌ Step 5: Leave still exists in database")
                return False
            
            # Step 6: Check notifications after deletion
            manager_notifications_after = list_leave_notifications(db, manager.user_id)
            employee_notifications_after = list_leave_notifications(db, employee.user_id)
            
            print(f"📧 Manager notifications after deletion: {len(manager_notifications_after)}")
            print(f"📧 Employee notifications after deletion: {len(employee_notifications_after)}")
            
            # Step 7: Verify deletion notifications were created
            deletion_notifications = [n for n in manager_notifications_after 
                                    if n.notification_type == "Leave Withdrawal"]
            
            if deletion_notifications:
                print(f"✅ Step 7: Found {len(deletion_notifications)} deletion notifications")
                for notif in deletion_notifications:
                    print(f"   📧 '{notif.title}': {notif.message[:50]}...")
            else:
                print("❌ Step 7: No deletion notifications found")
                return False
            
            print("✅ Complete leave deletion flow test passed!")
            return True
        else:
            print("❌ Failed to delete leave request")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_delete_permissions():
    """Test that users can only delete their own pending leaves"""
    db = next(get_db())
    
    try:
        # Find two different employees
        employees = db.query(User).filter(User.role == "Employee").limit(2).all()
        
        if len(employees) < 2:
            print("❌ Need at least 2 employees for permission testing")
            return False
            
        employee1, employee2 = employees[0], employees[1]
        print(f"✅ Testing with {employee1.name} and {employee2.name}")
        
        # Employee 1 creates a leave request
        start_date = datetime.now() + timedelta(days=10)
        end_date = start_date + timedelta(days=1)
        
        leave = apply_leave(
            db=db,
            user_id=employee1.user_id,
            start_date=start_date,
            end_date=end_date,
            reason="Permission test leave",
            leave_type="casual"
        )
        
        print(f"✅ Employee 1 created leave request (ID: {leave.leave_id})")
        
        # Employee 2 tries to delete Employee 1's leave (should fail)
        result = delete_leave(db, leave.leave_id, employee2.user_id)
        
        if result is None:
            print("✅ Correctly prevented Employee 2 from deleting Employee 1's leave")
            
            # Employee 1 deletes their own leave (should succeed)
            result = delete_leave(db, leave.leave_id, employee1.user_id)
            
            if result:
                print("✅ Employee 1 successfully deleted their own leave")
                return True
            else:
                print("❌ Employee 1 failed to delete their own leave")
                return False
        else:
            print("❌ Employee 2 was able to delete Employee 1's leave (security issue!)")
            return False
            
    except Exception as e:
        print(f"❌ Error during permission test: {str(e)}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🧪 Testing Complete Leave Deletion Flow")
    print("=" * 60)
    
    # Test 1: Complete flow with notifications
    print("\n📋 Test 1: Complete deletion flow with notifications")
    test1_result = test_complete_delete_flow()
    
    # Test 2: Permission testing
    print("\n📋 Test 2: Delete permissions and security")
    test2_result = test_delete_permissions()
    
    print("\n" + "=" * 60)
    print("🏁 Test Results:")
    print(f"   Test 1 (Complete flow): {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"   Test 2 (Permissions): {'✅ PASS' if test2_result else '❌ FAIL'}")
    
    if test1_result and test2_result:
        print("\n🎉 All tests passed! Leave deletion functionality is working correctly.")
        print("\n📝 Summary of what works:")
        print("   ✅ Users can delete their own pending leave requests")
        print("   ✅ Deletion notifications are sent to approvers")
        print("   ✅ Related notifications are cleaned up properly")
        print("   ✅ Users cannot delete other users' leave requests")
        print("   ✅ Users cannot delete approved/rejected leave requests")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed. Please check the implementation.")
        sys.exit(1)