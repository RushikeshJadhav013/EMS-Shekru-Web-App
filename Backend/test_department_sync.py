#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models.user import User
from app.db.models.department import Department
from sqlalchemy import func

def test_department_sync():
    """Test the department sync functionality"""
    
    # Get database session
    db = next(get_db())
    
    try:
        print("🔍 Testing department sync functionality...")
        
        # Check if we can query users
        print("📊 Checking users table...")
        users = db.query(User).limit(5).all()
        print(f"✅ Found {len(users)} users (showing first 5)")
        for user in users:
            print(f"   - {user.name} ({user.department})")
        
        # Check unique departments from users
        print("\n📋 Checking unique departments from users...")
        user_departments = (
            db.query(User.department, func.count(User.user_id).label('count'))
            .filter(User.department.isnot(None))
            .filter(User.department != '')
            .group_by(User.department)
            .all()
        )
        
        print(f"✅ Found {len(user_departments)} unique departments:")
        for dept_name, count in user_departments:
            print(f"   - {dept_name}: {count} users")
        
        # Check existing departments table
        print("\n🏢 Checking existing departments table...")
        existing_departments = db.query(Department).all()
        print(f"✅ Found {len(existing_departments)} existing departments:")
        for dept in existing_departments:
            print(f"   - {dept.name} (code: {dept.code})")
        
        # Test the sync logic
        print("\n🔄 Testing sync logic...")
        existing_dept_names = {dept.name.lower(): dept for dept in existing_departments}
        
        created_count = 0
        departments_to_create = []
        
        for dept_name, user_count in user_departments:
            dept_name_lower = dept_name.lower()
            
            if dept_name_lower not in existing_dept_names:
                # Generate a code from the department name
                code = ''.join(word[0].upper() for word in dept_name.split()[:3])
                if not code:
                    code = dept_name[:3].upper()
                
                # Ensure code is unique
                base_code = code
                counter = 1
                while db.query(Department).filter(Department.code == code).first():
                    code = f"{base_code}{counter}"
                    counter += 1
                
                departments_to_create.append({
                    'name': dept_name,
                    'code': code,
                    'user_count': user_count
                })
                created_count += 1
        
        print(f"📝 Would create {created_count} new departments:")
        for dept in departments_to_create:
            print(f"   - {dept['name']} (code: {dept['code']}, users: {dept['user_count']})")
        
        print("\n✅ Department sync test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during department sync test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_department_sync()
    if success:
        print("🎉 Department sync test passed!")
    else:
        print("💥 Department sync test failed!")
        sys.exit(1)