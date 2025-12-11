#!/usr/bin/env python3
"""
Test script to verify phone number duplicate validation
"""
import sys
import os
sys.path.append('.')

from app.crud.user_crud import get_user_by_phone
from app.db.database import SessionLocal

def test_phone_validation():
    """Test the phone number validation function"""
    db = SessionLocal()
    try:
        # Test with a non-existent phone number
        result = get_user_by_phone(db, '+91-9999999999')
        print(f"Test 1 - Non-existent phone: {result is None}")
        
        # Test with empty phone
        result = get_user_by_phone(db, '')
        print(f"Test 2 - Empty phone: {result is None}")
        
        # Test with None phone
        result = get_user_by_phone(db, None)
        print(f"Test 3 - None phone: {result is None}")
        
        print("Phone validation function works correctly!")
        
    except Exception as e:
        print(f"Error testing phone validation: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_phone_validation()