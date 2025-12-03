"""
Script to create the online_status_logs table in the database.
Run this script to add the new table without affecting existing data.
"""

from app.db.database import engine
from app.db.models.online_status import OnlineStatus
from app.db.database import Base

def create_table():
    try:
        # Create only the online_status_logs table
        OnlineStatus.__table__.create(bind=engine, checkfirst=True)
        print("✅ Successfully created online_status_logs table")
        print("   Table structure:")
        print("   - id (Primary Key)")
        print("   - attendance_id (Foreign Key to attendances)")
        print("   - user_id (Foreign Key to users)")
        print("   - is_online (Boolean)")
        print("   - reason (Text, nullable)")
        print("   - timestamp (DateTime with timezone)")
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        print("   The table might already exist, which is fine.")

if __name__ == "__main__":
    print("Creating online_status_logs table...")
    create_table()
