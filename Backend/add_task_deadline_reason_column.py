#!/usr/bin/env python3
"""
Migration script to add task_deadline_reason column to attendance table
"""
import sqlite3
import os
from datetime import datetime

def add_task_deadline_reason_column():
    """Add task_deadline_reason column to attendance table if it doesn't exist"""
    
    db_path = "attendance.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database file {db_path} not found!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(attendances)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'task_deadline_reason' in columns:
            print("✅ task_deadline_reason column already exists in attendances table")
            return True
        
        # Add the column
        cursor.execute("""
            ALTER TABLE attendances 
            ADD COLUMN task_deadline_reason TEXT
        """)
        
        conn.commit()
        print("✅ Successfully added task_deadline_reason column to attendances table")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(attendances)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'task_deadline_reason' in columns:
            print("✅ Column verified successfully")
            return True
        else:
            print("❌ Column verification failed")
            return False
            
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        if conn:
            conn.close()

def check_attendance_table_structure():
    """Check the current structure of the attendance table"""
    
    db_path = "attendance.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database file {db_path} not found!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table structure
        cursor.execute("PRAGMA table_info(attendances)")
        columns = cursor.fetchall()
        
        print("\n📋 Current attendances table structure:")
        print("-" * 60)
        for column in columns:
            cid, name, type_, notnull, default, pk = column
            nullable = "NOT NULL" if notnull else "NULL"
            primary = "PRIMARY KEY" if pk else ""
            print(f"{name:<25} {type_:<15} {nullable:<10} {primary}")
        
        print("-" * 60)
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Task Deadline Reason Column Migration")
    print("=" * 50)
    
    # Check current table structure
    check_attendance_table_structure()
    
    # Add the column if needed
    print("\n🔄 Adding task_deadline_reason column...")
    success = add_task_deadline_reason_column()
    
    if success:
        # Check structure again to confirm
        check_attendance_table_structure()
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed!")