#!/usr/bin/env python3
"""
Create sample tasks with different deadlines for testing the warning system
"""
from app.db.database import SessionLocal
from app.db.models.task import Task
from app.db.models.user import User
from datetime import datetime, date, timedelta
from app.enums import TaskStatus

def create_sample_tasks():
    """Create sample tasks with various deadlines"""
    
    db = SessionLocal()
    try:
        # Get any existing user for testing
        user = db.query(User).filter(User.role == "employee").first()
        if not user:
            # Try to find any user
            user = db.query(User).first()
        
        if not user:
            print("❌ No users found in database. Please create a user first.")
            return
        else:
            print(f"✅ Using existing user: {user.name} (ID: {user.user_id})")

        # Get any admin user to assign tasks
        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            # Use the same user as admin for testing
            admin = user
            print(f"✅ Using user as admin: {admin.name} (ID: {admin.user_id})")
        else:
            print(f"✅ Using existing admin: {admin.name} (ID: {admin.user_id})")

        # Create sample tasks with different deadlines
        today = date.today()
        
        sample_tasks = [
            {
                "title": "Complete API Documentation",
                "description": "Write comprehensive API documentation for the new endpoints",
                "due_date": today,  # Due today
                "status": TaskStatus.IN_PROGRESS,
                "priority": "High"
            },
            {
                "title": "Fix Login Bug",
                "description": "Resolve the authentication issue reported by users",
                "due_date": today,  # Due today
                "status": TaskStatus.PENDING,
                "priority": "Urgent"
            },
            {
                "title": "Update User Interface",
                "description": "Implement the new design changes for the dashboard",
                "due_date": today + timedelta(days=1),  # Due tomorrow
                "status": TaskStatus.PENDING,
                "priority": "Medium"
            },
            {
                "title": "Database Optimization",
                "description": "Optimize database queries for better performance",
                "due_date": today + timedelta(days=2),  # Due in 2 days
                "status": TaskStatus.PENDING,
                "priority": "Medium"
            },
            {
                "title": "Code Review",
                "description": "Review pull requests from team members",
                "due_date": today + timedelta(days=3),  # Due in 3 days
                "status": TaskStatus.PENDING,
                "priority": "Low"
            },
            {
                "title": "Overdue Task",
                "description": "This task was supposed to be completed yesterday",
                "due_date": today - timedelta(days=1),  # Overdue
                "status": TaskStatus.IN_PROGRESS,
                "priority": "High"
            }
        ]

        created_tasks = []
        for task_data in sample_tasks:
            # Check if task already exists
            existing_task = db.query(Task).filter(
                Task.title == task_data["title"],
                Task.assigned_to == user.user_id
            ).first()
            
            if not existing_task:
                task = Task(
                    title=task_data["title"],
                    description=task_data["description"],
                    assigned_by=admin.user_id,
                    assigned_to=user.user_id,
                    status=task_data["status"],
                    priority=task_data["priority"],
                    due_date=datetime.combine(task_data["due_date"], datetime.min.time()),
                    created_at=datetime.utcnow()
                )
                db.add(task)
                created_tasks.append(task)
            else:
                print(f"⚠️ Task '{task_data['title']}' already exists")

        if created_tasks:
            db.commit()
            print(f"\n✅ Created {len(created_tasks)} sample tasks:")
            for task in created_tasks:
                days_diff = (task.due_date.date() - today).days
                if days_diff < 0:
                    deadline_info = f"Overdue by {abs(days_diff)} day(s)"
                elif days_diff == 0:
                    deadline_info = "Due today"
                else:
                    deadline_info = f"Due in {days_diff} day(s)"
                
                print(f"  - {task.title} ({deadline_info}) - {task.status} - {task.priority}")
        else:
            print("ℹ️ All sample tasks already exist")

        print(f"\n📊 Task Summary for user {user.name}:")
        all_tasks = db.query(Task).filter(Task.assigned_to == user.user_id).all()
        print(f"  Total tasks: {len(all_tasks)}")
        
        # Count by deadline
        overdue = sum(1 for t in all_tasks if t.due_date and t.due_date.date() < today and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED])
        due_today = sum(1 for t in all_tasks if t.due_date and t.due_date.date() == today and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED])
        upcoming = sum(1 for t in all_tasks if t.due_date and t.due_date.date() > today and t.due_date.date() <= today + timedelta(days=3) and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED])
        
        print(f"  Overdue: {overdue}")
        print(f"  Due today: {due_today}")
        print(f"  Upcoming (next 3 days): {upcoming}")

    except Exception as e:
        print(f"❌ Error creating sample tasks: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Creating Sample Tasks for Testing")
    print("=" * 50)
    create_sample_tasks()
    print("\n✅ Sample task creation complete!")