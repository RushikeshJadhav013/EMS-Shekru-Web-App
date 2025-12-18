#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings

def remove_budget_column():
    """Remove the budget column from departments table"""
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        # Check if budget column exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COLUMN_NAME 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'departments'
                AND COLUMN_NAME = 'budget';
            """))
            column_exists = result.fetchone() is not None
        
        if not column_exists:
            print("✅ Budget column does not exist in departments table")
            return True
        
        print("🗑️ Removing budget column from departments table...")
        
        # Remove the budget column
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE departments DROP COLUMN budget"))
            conn.commit()
        
        print("✅ Budget column removed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error removing budget column: {e}")
        return False

if __name__ == "__main__":
    success = remove_budget_column()
    if success:
        print("🎉 Budget column removal completed!")
    else:
        print("💥 Budget column removal failed!")
        sys.exit(1)