"""
Database Migration Script: Add employee_type column to users table

This script adds the employee_type column to the existing users table.
Run this ONCE to update your database schema.

Usage:
    python add_employee_type_column.py
"""

from sqlalchemy import create_engine, text
from app.core.config import settings

def add_employee_type_column():
    """Add employee_type column to users table if it doesn't exist"""
    
    # Create database engine
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            # Check if column already exists
            result = connection.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='employee_type'
            """))
            
            if result.fetchone():
                print("✅ Column 'employee_type' already exists in 'users' table")
                return
            
            # Add the column
            print("Adding 'employee_type' column to 'users' table...")
            connection.execute(text("""
                ALTER TABLE users 
                ADD COLUMN employee_type VARCHAR(50) NULL
            """))
            connection.commit()
            
            print("✅ Successfully added 'employee_type' column to 'users' table")
            print("   - Column type: VARCHAR(50)")
            print("   - Nullable: Yes")
            print("   - Default: NULL")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("=" * 60)
    print("Database Migration: Add employee_type Column")
    print("=" * 60)
    add_employee_type_column()
    print("=" * 60)
    print("Migration completed!")
    print("=" * 60)
