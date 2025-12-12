#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.crud.leave_crud import list_decided_by_approver
from app.db.models.user import User
from app.enums import RoleEnum
import traceback

def test_leave_approvals():
    db = SessionLocal()
    try:
        print("Testing leave approvals history...")
        
        # Get an admin user for testing
        admin_user = db.query(User).filter(User.role == RoleEnum.ADMIN).first()
        if not admin_user:
            print("No admin user found")
            return
            
        print(f"Testing with admin user: {admin_user.name} (ID: {admin_user.user_id})")
        
        # Test the function that's causing issues
        decided_leaves = list_decided_by_approver(db, admin_user.user_id)
        print(f"Found {len(decided_leaves)} decided leaves")
        
        # Test accessing user details
        for leave in decided_leaves[:3]:  # Test first 3
            print(f"Leave ID: {leave.leave_id}, User: {leave.user.name if leave.user else 'No user'}")
        
        print("Success!")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Full traceback:")
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_leave_approvals()