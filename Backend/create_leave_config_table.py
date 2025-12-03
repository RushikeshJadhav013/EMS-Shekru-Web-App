"""
Migration script to create leave_allocation_config table.
Run this script to add the leave configuration feature to your database.
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://staffly:staffly123@localhost/staffly_db")

# Create engine
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# Define the table
class LeaveAllocationConfig(Base):
    __tablename__ = "leave_allocation_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    total_annual_leave = Column(Integer, nullable=False, default=15)
    sick_leave_allocation = Column(Integer, nullable=False, default=10)
    casual_leave_allocation = Column(Integer, nullable=False, default=5)
    other_leave_allocation = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by = Column(Integer, nullable=True)

def create_table():
    """Create the leave_allocation_config table"""
    try:
        print("Creating leave_allocation_config table...")
        Base.metadata.create_all(bind=engine, tables=[LeaveAllocationConfig.__table__])
        print("✅ Table created successfully!")
        
        # Create a default configuration
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        try:
            # Check if a configuration already exists
            existing = db.query(LeaveAllocationConfig).first()
            
            if not existing:
                print("\nCreating default leave allocation configuration...")
                default_config = LeaveAllocationConfig(
                    total_annual_leave=15,
                    sick_leave_allocation=10,
                    casual_leave_allocation=5,
                    other_leave_allocation=0,
                    is_active=True
                )
                db.add(default_config)
                db.commit()
                print("✅ Default configuration created!")
                print(f"   - Total Annual Leave: 15 days")
                print(f"   - Sick Leave: 10 days")
                print(f"   - Casual Leave: 5 days")
                print(f"   - Other Leave: 0 days")
            else:
                print("\n⚠️  Configuration already exists, skipping default creation.")
        
        finally:
            db.close()
        
        print("\n🎉 Migration completed successfully!")
        print("\nNext steps:")
        print("1. Restart your backend server")
        print("2. Login as admin")
        print("3. Go to Leave Management > Leave Calendar")
        print("4. Configure leave allocation in the new panel")
        
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        raise

if __name__ == "__main__":
    create_table()
