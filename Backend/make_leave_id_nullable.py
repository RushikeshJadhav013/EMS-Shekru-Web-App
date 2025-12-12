#!/usr/bin/env python3

"""
Migration script to make leave_id nullable in leave_notifications table.
This allows deletion notifications to persist after the leave is deleted.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.database import get_db

def make_leave_id_nullable():
    """Make leave_id column nullable in leave_notifications table"""
    db = next(get_db())
    
    try:
        print("🔧 Making leave_id nullable in leave_notifications table...")
        
        # Check current schema
        result = db.execute(text("DESCRIBE leave_notifications"))
        columns = result.fetchall()
        
        print("📋 Current schema:")
        for col in columns:
            if col[0] == 'leave_id':
                print(f"   leave_id: {col[1]} {col[2]} {col[3]} {col[4]} {col[5]}")
        
        # Modify the column to allow NULL
        db.execute(text("ALTER TABLE leave_notifications MODIFY COLUMN leave_id INT NULL"))
        db.commit()
        
        print("✅ Successfully made leave_id nullable")
        
        # Verify the change
        result = db.execute(text("DESCRIBE leave_notifications"))
        columns = result.fetchall()
        
        print("📋 Updated schema:")
        for col in columns:
            if col[0] == 'leave_id':
                print(f"   leave_id: {col[1]} {col[2]} {col[3]} {col[4]} {col[5]}")
                
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 Database Migration: Make leave_id nullable")
    print("=" * 50)
    
    success = make_leave_id_nullable()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("   - leave_id column in leave_notifications is now nullable")
        print("   - Deletion notifications will persist after leave deletion")
    else:
        print("\n💥 Migration failed!")
        sys.exit(1)