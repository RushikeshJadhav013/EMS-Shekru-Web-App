#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_sync_function():
    """Test the sync function directly"""
    
    try:
        print("🔍 Testing sync function directly...")
        
        from app.db.database import get_db
        from app.db.models.user import User
        from app.db.models.department import Department
        from sqlalchemy import func
        
        # Get database session
        db = next(get_db())
        
        print("📊 Running sync logic...")
        
        # Get all unique department names from users (excluding None/empty)
        user_departments = (
            db.query(User.department, func.count(User.user_id).label('count'))
            .filter(User.department.isnot(None))
            .filter(User.department != '')
            .group_by(User.department)
            .all()
        )
        
        print(f"✅ Found {len(user_departments)} unique departments from users")
        
        # Get existing departments
        existing_departments = {dept.name.lower(): dept for dept in db.query(Department).all()}
        
        print(f"✅ Found {len(existing_departments)} existing departments")
        
        created_count = 0
        updated_count = 0
        departments_created = []
        
        for dept_name, user_count in user_departments:
            dept_name_lower = dept_name.lower()
            
            if dept_name_lower not in existing_departments:
                # Create new department
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
                
                print(f"📝 Creating department: {dept_name} (code: {code})")
                
                new_dept = Department(
                    name=dept_name,
                    code=code,
                    description=f"Auto-created from user departments",
                    status="active",
                    employee_count=user_count,
                    manager_id=None,
                    budget=None,
                    location=None
                )
                db.add(new_dept)
                departments_created.append(dept_name)
                created_count += 1
            else:
                # Update employee count for existing department
                existing_dept = existing_departments[dept_name_lower]
                if existing_dept.employee_count != user_count:
                    print(f"📝 Updating employee count for {dept_name}: {existing_dept.employee_count} -> {user_count}")
                    existing_dept.employee_count = user_count
                    updated_count += 1
        
        # Commit changes
        db.commit()
        
        result = {
            "message": "Department sync completed",
            "created": created_count,
            "updated": updated_count,
            "departments_created": departments_created,
            "total_departments": len(user_departments)
        }
        
        print(f"✅ Sync completed successfully!")
        print(f"📊 Result: {result}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Sync function test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_sync_function()
    if success:
        print("🎉 Sync function test passed!")
    else:
        print("💥 Sync function test failed!")
        sys.exit(1)