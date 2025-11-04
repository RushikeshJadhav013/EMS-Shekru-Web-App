#!/usr/bin/env python3
"""
Migration script to replace is_verified column with is_active column
This will:
1. Check if is_verified exists
2. Drop is_verified column
3. Ensure is_active column exists
"""
from sqlalchemy import text
from app.db.database import engine

def replace_is_verified_with_is_active():
    """Replace is_verified column with is_active column"""
    try:
        with engine.connect() as connection:
            # Check if is_verified column exists
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'users' 
                AND COLUMN_NAME = 'is_verified'
            """))
            
            is_verified_exists = result.scalar() > 0
            
            if is_verified_exists:
                print("📋 Found 'is_verified' column, removing it...")
                # Drop is_verified column
                connection.execute(text("""
                    ALTER TABLE users 
                    DROP COLUMN is_verified
                """))
                connection.commit()
                print("✅ Successfully removed 'is_verified' column")
            else:
                print("ℹ️  'is_verified' column doesn't exist (already removed)")
            
            # Check if is_active column exists
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'users' 
                AND COLUMN_NAME = 'is_active'
            """))
            
            is_active_exists = result.scalar() > 0
            
            if is_active_exists:
                print("✅ 'is_active' column already exists")
            else:
                # Add is_active column
                print("📋 Adding 'is_active' column...")
                connection.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL
                """))
                connection.commit()
                print("✅ Successfully added 'is_active' column")
                print("✅ All existing employees are set to 'active' by default")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    print("=" * 60)
    print("Migration: Replace is_verified with is_active")
    print("=" * 60)
    replace_is_verified_with_is_active()
    print("\n" + "=" * 60)
    print("✅ Migration complete!")
    print("=" * 60)
