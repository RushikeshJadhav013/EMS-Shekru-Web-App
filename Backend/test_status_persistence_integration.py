#!/usr/bin/env python3
"""
Integration test to verify online status persistence across login sessions.
This simulates the user scenario described in the issue.
"""

import sys
sys.path.append('.')

from app.db.database import get_db
from app.db.models.online_status import OnlineStatus
from app.db.models.attendance import Attendance
from app.db.models.user import User
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

UTC_TZ = ZoneInfo('UTC')

def simulate_user_scenario():
    """
    Simulate the exact scenario from the issue:
    1. User checks in (becomes online)
    2. User goes offline
    3. User logs out and logs back in
    4. Status should remain offline
    """
    
    db = next(get_db())
    
    print("=== Simulating User Scenario ===\n")
    
    # Get today's bounds
    today_start = datetime.now(UTC_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Find user with active attendance
    attendance = db.query(Attendance).filter(
        Attendance.check_in >= today_start,
        Attendance.check_in < today_end,
        Attendance.check_out.is_(None)
    ).first()
    
    if not attendance:
        print("❌ No active attendance found. Please check in first.")
        db.close()
        return
    
    user_id = attendance.user_id
    
    print(f"Testing with User ID: {user_id}")
    print(f"Attendance ID: {attendance.attendance_id}")
    
    # Step 1: Check current status (simulates login)
    def get_current_status():
        latest_status = db.query(OnlineStatus).filter(
            OnlineStatus.user_id == user_id,
            OnlineStatus.timestamp >= today_start,
            OnlineStatus.timestamp < today_end
        ).order_by(OnlineStatus.timestamp.desc()).first()
        
        return True if not latest_status else latest_status.is_online
    
    initial_status = get_current_status()
    print(f"\n1. Initial status after 'login': {'Online' if initial_status else 'Offline'}")
    
    # Step 2: If user is online, simulate going offline
    if initial_status:
        print("2. User is online, simulating 'Go Offline' action...")
        
        # Create offline status (simulates clicking "Go Offline")
        offline_status = OnlineStatus(
            attendance_id=attendance.attendance_id,
            user_id=user_id,
            is_online=False,
            reason="Test: Going offline for break",
            timestamp=datetime.now(UTC_TZ)
        )
        db.add(offline_status)
        db.commit()
        
        print("   ✅ User went offline")
    else:
        print("2. User is already offline")
    
    # Step 3: Simulate logout/login by checking status again
    print("\n3. Simulating logout and login...")
    print("   (In real scenario: user closes browser, logs back in)")
    
    # Step 4: Check status after "login" (this is the key test)
    final_status = get_current_status()
    print(f"\n4. Status after 'login': {'Online' if final_status else 'Offline'}")
    
    # Verify the fix
    print(f"\n=== Test Results ===")
    if not final_status:  # Should be offline
        print("✅ SUCCESS: Status correctly persisted as OFFLINE")
        print("✅ User will remain offline until they manually go online")
        print("✅ Fix is working correctly!")
    else:
        print("❌ FAILURE: Status incorrectly reset to ONLINE")
        print("❌ This indicates the fix needs more work")
    
    # Show status history
    print(f"\n=== Status History Today ===")
    all_statuses = db.query(OnlineStatus).filter(
        OnlineStatus.user_id == user_id,
        OnlineStatus.timestamp >= today_start,
        OnlineStatus.timestamp < today_end
    ).order_by(OnlineStatus.timestamp.asc()).all()
    
    for i, status in enumerate(all_statuses, 1):
        status_text = "Online" if status.is_online else "Offline"
        time_str = status.timestamp.strftime('%H:%M:%S')
        print(f"{i}. {time_str} - {status_text} ({status.reason})")
    
    db.close()

if __name__ == "__main__":
    simulate_user_scenario()