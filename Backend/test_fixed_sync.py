#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_fixed_sync():
    """Test the fixed sync function from routes"""
    
    try:
        print("🔍 Testing fixed sync function...")
        
        from app.db.database import get_db
        from app.routes.department_routes import sync_departments_from_users
        from app.db.models.user import User
        from app.enums import RoleEnum
        
        # Get database session
        db = next(get_db())
        
        # Create a mock user with admin role for the dependency
        class MockUser:
            def __init__(self):
                self.role = RoleEnum.ADMIN
                self.name = "Test Admin"
        
        mock_user = MockUser()
        
        print("📊 Running actual sync function...")
        
        # Call the actual sync function
        result = sync_departments_from_users(db, mock_user)
        
        print(f"✅ Sync completed successfully!")
        print(f"📊 Result: {result}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Fixed sync test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_fixed_sync()
    if success:
        print("🎉 Fixed sync test passed!")
    else:
        print("💥 Fixed sync test failed!")
        sys.exit(1)