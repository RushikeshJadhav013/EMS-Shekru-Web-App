#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_db
from app.db.models.user import User
from app.enums import RoleEnum
from jose import jwt
from app.core.config import settings

def test_sync_endpoint():
    """Test the sync endpoint directly"""
    
    client = TestClient(app)
    
    # Get a test user (admin or HR)
    db = next(get_db())
    
    try:
        # Find an admin or HR user
        admin_user = db.query(User).filter(
            User.role.in_([RoleEnum.ADMIN, RoleEnum.HR])
        ).first()
        
        if not admin_user:
            print("❌ No admin or HR user found. Creating a test admin user...")
            # For testing, we'll just use any user and assume they have permission
            admin_user = db.query(User).first()
            if not admin_user:
                print("❌ No users found in database!")
                return False
        
        print(f"✅ Using user: {admin_user.name} ({admin_user.role})")
        
        # Create a JWT token for the user
        token_data = {"sub": admin_user.email}
        token = jwt.encode(token_data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        
        # Test the sync endpoint
        print("🔄 Testing sync endpoint...")
        response = client.post(
            "/departments/sync-from-users",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📋 Response content: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Sync endpoint works correctly!")
            return True
        else:
            print(f"❌ Sync endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing sync endpoint: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_sync_endpoint()
    if success:
        print("🎉 Sync endpoint test passed!")
    else:
        print("💥 Sync endpoint test failed!")
        sys.exit(1)