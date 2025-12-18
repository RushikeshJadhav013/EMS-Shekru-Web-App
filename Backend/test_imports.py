#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all the imports used in the department sync endpoint"""
    
    try:
        print("🔍 Testing imports...")
        
        # Test basic imports
        print("📦 Testing basic imports...")
        from app.db.database import get_db
        from app.db.models.user import User
        from app.enums import RoleEnum
        print("✅ Basic imports successful")
        
        # Test department imports
        print("📦 Testing department imports...")
        from app.db.models.department import Department
        print("✅ Department model import successful")
        
        # Test department routes imports
        print("📦 Testing department routes imports...")
        from app.routes.department_routes import sync_departments_from_users
        print("✅ Department routes import successful")
        
        # Test SQLAlchemy func
        print("📦 Testing SQLAlchemy func...")
        from sqlalchemy import func
        print("✅ SQLAlchemy func import successful")
        
        # Test database connection
        print("📦 Testing database connection...")
        db = next(get_db())
        
        # Test basic queries
        print("📊 Testing basic queries...")
        user_count = db.query(User).count()
        print(f"✅ Found {user_count} users in database")
        
        dept_count = db.query(Department).count()
        print(f"✅ Found {dept_count} departments in database")
        
        db.close()
        
        print("✅ All imports and basic functionality working!")
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("🎉 Import test passed!")
    else:
        print("💥 Import test failed!")
        sys.exit(1)