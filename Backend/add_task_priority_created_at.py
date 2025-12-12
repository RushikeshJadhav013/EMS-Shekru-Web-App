#!/usr/bin/env python3
"""
Add priority and created_at columns to tasks table
"""

import sys
import os
from datetime import datetime

# Add the Backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.database import get_db

def add_task_columns():
    """Add missing columns to tasks table"""
    print("Adding missing columns to tasks table...")
    
    db = next(get_db())
    
    try:
        # Check if priority column exists
        result = db.execute(text("""
            SELECT COUNT(*) as cnt 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'tasks' 
            AND COLUMN_NAME = 'priority'
        """))
        priority_exists = result.fetchone()[0] > 0
        
        # Check if created_at column exists
        result = db.execute(text("""
            SELECT COUNT(*) as cnt 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'tasks' 
            AND COLUMN_NAME = 'created_at'
        """))
        created_at_exists = result.fetchone()[0] > 0
        
        # Add priority column if it doesn't exist
        if not priority_exists:
            print("Adding priority column...")
            db.execute(text("ALTER TABLE tasks ADD COLUMN priority VARCHAR(20) DEFAULT 'Medium'"))
            # Update existing tasks to have Medium priority
            db.execute(text("UPDATE tasks SET priority = 'Medium' WHERE priority IS NULL"))
            print("✅ Priority column added")
        else:
            print("✅ Priority column already exists")
        
        # Add created_at column if it doesn't exist
        if not created_at_exists:
            print("Adding created_at column...")
            db.execute(text("ALTER TABLE tasks ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
            # Update existing tasks to have a created_at timestamp (use current time as fallback)
            db.execute(text("UPDATE tasks SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
            print("✅ Created_at column added")
        else:
            print("✅ Created_at column already exists")
        
        db.commit()
        print("✅ Database migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    add_task_columns()