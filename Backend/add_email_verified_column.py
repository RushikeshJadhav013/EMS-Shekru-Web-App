"""
Migration script to add is_email_verified column to users table
Run: python add_email_verified_column.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.database import engine

def add_email_verified_column():
    """Add is_email_verified column to users table"""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'is_email_verified'
        """))
        exists = result.scalar() > 0
        
        if exists:
            print("✅ Column 'is_email_verified' already exists")
            return
        
        # Add column
        conn.execute(text("""
            ALTER TABLE users ADD COLUMN is_email_verified BOOLEAN DEFAULT FALSE
        """))
        conn.commit()
        print("✅ Added 'is_email_verified' column to users table")

if __name__ == "__main__":
    add_email_verified_column()
