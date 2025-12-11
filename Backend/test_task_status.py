"""
Test script to check task status values in database
"""
from app.db.database import SessionLocal
from app.db.models.task import Task
from sqlalchemy import func

def check_task_status():
    db = SessionLocal()
    try:
        # Get all tasks
        all_tasks = db.query(Task).all()
        print(f"\n=== Total Tasks: {len(all_tasks)} ===\n")
        
        for task in all_tasks:
            print(f"Task ID: {task.task_id}")
            print(f"  Title: {task.title}")
            print(f"  Status: '{task.status}' (type: {type(task.status).__name__})")
            print(f"  Status repr: {repr(task.status)}")
            print()
        
        # Count by status
        print("\n=== Status Counts ===")
        status_counts = db.query(Task.status, func.count(Task.task_id)).group_by(Task.status).all()
        for status, count in status_counts:
            print(f"Status '{status}': {count} tasks")
        
        # Test the query used in dashboard
        print("\n=== Testing Dashboard Query ===")
        from app.enums import TaskStatus
        
        # Test with .value
        active_with_value = db.query(func.count(Task.task_id)).filter(
            Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value])
        ).scalar() or 0
        print(f"Active tasks (using .value): {active_with_value}")
        
        # Test with direct strings
        active_with_strings = db.query(func.count(Task.task_id)).filter(
            Task.status.in_(["Pending", "In Progress"])
        ).scalar() or 0
        print(f"Active tasks (using strings): {active_with_strings}")
        
        # Test individual statuses
        pending_count = db.query(func.count(Task.task_id)).filter(Task.status == "Pending").scalar() or 0
        in_progress_count = db.query(func.count(Task.task_id)).filter(Task.status == "In Progress").scalar() or 0
        completed_count = db.query(func.count(Task.task_id)).filter(Task.status == "Completed").scalar() or 0
        
        print(f"\nPending: {pending_count}")
        print(f"In Progress: {in_progress_count}")
        print(f"Completed: {completed_count}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_task_status()
