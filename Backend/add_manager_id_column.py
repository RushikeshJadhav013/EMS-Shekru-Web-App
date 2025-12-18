#!/usr/bin/env python3
"""
Add manager_id column to users table for reporting manager functionality
"""

import sys
import os

# Add the Backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def add_manager_id_column():
    """Add manager_id column to users table"""
    
    try:
        from sqlalchemy import create_engine, text
        from app.core.config import settings
        
        print("🔧 Connecting to database...")
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as connection:
            # Check if column already exists
            print("📝 Checking if manager_id column exists...")
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'users' 
                AND column_name = 'manager_id'
            """))
            column_exists = result.fetchone()[0]
            
            if column_exists:
                print("✅ manager_id column already exists in users table")
                return True
            
            # Add manager_id column
            print("📝 Adding manager_id column to users table...")
            connection.execute(text("""
                ALTER TABLE users 
                ADD COLUMN manager_id INTEGER NULL
            """))
            
            # Commit the transaction
            connection.commit()
            
            # Verify the column was added
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'users' 
                AND column_name = 'manager_id'
            """))
            column_exists = result.fetchone()[0]
            
            if column_exists:
                print("✅ Successfully added manager_id column to users table")
                
                # Show current table structure
                print("\n📋 Current users table columns:")
                result = connection.execute(text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'users'
                    ORDER BY ordinal_position
                """))
                for column in result.fetchall():
                    print(f"  - {column[0]} ({column[1]}) {'NULL' if column[2] == 'YES' else 'NOT NULL'}")
                
                return True
            else:
                print("❌ Failed to add manager_id column")
                return False
                
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Adding manager_id column to users table...")
    success = add_manager_id_column()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("💡 You can now assign reporting managers to employees")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)