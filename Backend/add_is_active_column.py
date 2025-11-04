#!/usr/bin/env python3
"""
Migration script to add is_active column to users table
Run this once to update your existing database
"""
from sqlalchemy import text
from app.db.database import engine

def add_is_active_column():
    """Add is_active column to users table if it doesn't exist"""
    try:
        with engine.connect() as connection:
            # Check if column exists
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'users' 
                AND COLUMN_NAME = 'is_active'
            """))
            
            column_exists = result.scalar() > 0
            
            if column_exists:
                print("✅ Column 'is_active' already exists in users table")
            else:
                # Add the column
                connection.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL
                """))
                connection.commit()
                print("✅ Successfully added 'is_active' column to users table")
                print("✅ All existing employees are set to 'active' by default")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    print("Adding is_active column to users table...")
    add_is_active_column()
    print("\n✅ Migration complete!")
