#!/usr/bin/env python3
"""
Debug script to test the task endpoint and see what's causing the 500 error
"""

import sys
import os
from datetime import datetime

# Add the Backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import get_db
from app.crud.task_crud import list_tasks
from app.schemas.task_schema import TaskOut
from app.db.models.user import User

def debug_task_endpoint():
    """Debug the task endpoint to find the 500 error"""
    print("Debugging task endpoint...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Get a test user (assuming user_id 1 exists)
        user = db.query(User).first()
        if not user:
            print("❌ No users found in database")
            return
            
        print(f"✅ Found user: {user.name} (ID: {user.user_id})")
        
        # Try to get tasks
        tasks = list_tasks(db, user.user_id)
        print(f"✅ Found {len(tasks)} tasks")
        
        # Try to validate each task with TaskOut schema
        for i, task in enumerate(tasks):
            try:
                print(f"\nValidating task {i+1}: {task.title}")
                print(f"  - task_id: {task.task_id}")
                print(f"  - assigned_to: {task.assigned_to}")
                print(f"  - assigned_by: {task.assigned_by}")
                print(f"  - due_date: {task.due_date}")
                print(f"  - status: {task.status}")
                print(f"  - priority: {task.priority}")
                print(f"  - created_at: {task.created_at}")
                
                # Try to create TaskOut object
                task_out = TaskOut.model_validate(task)
                print(f"  ✅ Task {i+1} validation successful")
                
            except Exception as e:
                print(f"  ❌ Task {i+1} validation failed: {e}")
                print(f"  Task data: {task.__dict__}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    debug_task_endpoint()