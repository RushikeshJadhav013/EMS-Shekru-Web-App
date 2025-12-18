#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings
from app.db.database import Base
from app.db.models.department import Department

def create_departments_table():
    """Create the departments table if it doesn't exist"""
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        # Check if table exists (MySQL version)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT TABLE_NAME 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'departments';
            """))
            table_exists = result.fetchone() is not None
        
        if table_exists:
            print("✅ Departments table already exists")
            return True
        
        print("📋 Creating departments table...")
        
        # Create the table
        Department.__table__.create(engine, checkfirst=True)
        
        print("✅ Departments table created successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error creating departments table: {e}")
        return False

if __name__ == "__main__":
    success = create_departments_table()
    if success:
        print("🎉 Department table setup completed!")
    else:
        print("💥 Department table setup failed!")
        sys.exit(1)