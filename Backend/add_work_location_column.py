"""
Migration script to add work_location column to attendances table
This tracks whether an employee is working from office or home
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text, Column, String
from app.core.config import settings

def add_work_location_column():
    """Add work_location column to attendances table"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM pragma_table_info('attendances') 
            WHERE name='work_location'
        """))
        
        if result.scalar() == 0:
            print("Adding work_location column to attendances table...")
            conn.execute(text("""
                ALTER TABLE attendances 
                ADD COLUMN work_location VARCHAR(50) DEFAULT 'office'
            """))
            conn.commit()
            print("✓ work_location column added successfully")
        else:
            print("✓ work_location column already exists")

if __name__ == "__main__":
    add_work_location_column()
