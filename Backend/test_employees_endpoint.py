"""
Test script to check if the employees endpoint works
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.db.database import SessionLocal
from app.crud.user_crud import list_users
from app.schemas.user_schema import UserOut

def test_list_users():
    db = SessionLocal()
    try:
        print("Testing list_users function...")
        users = list_users(db)
        print(f"✓ Found {len(users)} users")
        
        if users:
            print("\nFirst user:")
            user = users[0]
            print(f"  - ID: {user.user_id}")
            print(f"  - Name: {user.name}")
            print(f"  - Email: {user.email}")
            print(f"  - Role: {user.role}")
            print(f"  - Department: {user.department}")
            
            # Try to serialize to UserOut
            try:
                user_out = UserOut.model_validate(user)
                print(f"\n✓ Successfully serialized to UserOut")
                print(f"  Serialized data: {user_out.model_dump()}")
            except Exception as e:
                print(f"\n✗ Failed to serialize to UserOut: {e}")
                print(f"  User attributes: {dir(user)}")
                
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_list_users()
