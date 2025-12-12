#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.routes.attendance_routes import get_attendance_summary
import traceback

def test_attendance_summary():
    db = SessionLocal()
    try:
        print("Testing attendance summary...")
        result = get_attendance_summary(db)
        print("Success!")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        print("Full traceback:")
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_attendance_summary()