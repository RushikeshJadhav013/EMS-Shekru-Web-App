#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
from app.core.security import create_token
from app.db.models.user import User
from app.db.database import SessionLocal
from app.enums import RoleEnum
from datetime import timedelta

def test_leave_api():
    db = SessionLocal()
    try:
        # Get an admin user
        admin_user = db.query(User).filter(User.role == RoleEnum.ADMIN).first()
        if not admin_user:
            print("No admin user found")
            return
            
        # Create a token for the admin user
        token = create_token({"sub": admin_user.email, "role": str(admin_user.role)}, timedelta(hours=1))
        
        # Test the approvals history endpoint
        headers = {"Authorization": f"Bearer {token}"}
        
        print("Testing /leave/approvals/history endpoint...")
        response = requests.get("https://staffly.space/leave/approvals/history", headers=headers)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Found {len(data)} leave records")
            if data:
                print(f"Sample record: {data[0]}")
        else:
            print(f"Error: {response.text}")
            
        print("\nTesting /leave/approvals endpoint...")
        response = requests.get("https://staffly.space/leave/approvals", headers=headers)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Found {len(data)} pending leave records")
        else:
            print(f"Error: {response.text}")
            
        print("\nTesting /leave/?period=last_3_months endpoint...")
        response = requests.get("https://staffly.space/leave/?period=last_3_months", headers=headers)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Found {len(data)} user leave records")
            if data:
                print(f"Sample record: {data[0]}")
        else:
            print(f"Error: {response.text}")
            
        # Test with a user who has leave records
        print("\nTesting with a user who has leave records...")
        user_with_leaves = db.query(User).filter(User.user_id == 3).first()  # Mahesh Chole
        if user_with_leaves:
            user_token = create_token({"sub": user_with_leaves.email, "role": str(user_with_leaves.role)}, timedelta(hours=1))
            user_headers = {"Authorization": f"Bearer {user_token}"}
            
            response = requests.get("https://staffly.space/leave/?period=last_3_months", headers=user_headers)
            print(f"User leave records - Status Code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Success! User has {len(data)} leave records")
                if data:
                    print(f"Sample user record: {data[0]}")
            else:
                print(f"User leave error: {response.text}")
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Found {len(data)} leave records")
            if data:
                print(f"Sample record: {data[0]}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_leave_api()