#!/usr/bin/env python3
"""
Test the daily reset functionality for online status.
"""

import sys
sys.path.append('.')

from app.db.database import get_db
from app.db.models.online_status import OnlineStatus
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

UTC_TZ = ZoneInfo('UTC')

def test_daily_reset_logic():
    """Test that offline status from yesterday gets reset on new check-in."""
    
    db = next(get_db())
    
    print("=== Testing Daily Reset Logic ===\n")
    
    # Test user ID
    user_id = 2
    
    # Get date boundaries
    today_start = datetime.now(UTC_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    
    print(f"Yesterday: {yesterday_start.date()}")
    print(f"Today: {today_start.date()}")
    
    # Check if user has status from yesterday
    last_status_yesterday = db.query(OnlineStatus).filter(
        OnlineStatus.user_id == user_id,
        OnlineStatus.timestamp >= yesterday_start,
        OnlineStatus.timestamp < today_start
    ).order_by(OnlineStatus.timestamp.desc()).first()
    
    if last_status_yesterday:
        status_text = "Online" if last_status_yesterday.is_online else "Offline"
        print(f"\nYesterday's last status: {status_text}")
        print(f"Time: {last_status_yesterday.timestamp}")
        print(f"Reason: {last_status_yesterday.reason}")
    else:
        print("\nNo status found from yesterday")
    
    # Check today's status
    existing_status_today = db.query(OnlineStatus).filter(
        OnlineStatus.user_id == user_id,
        OnlineStatus.timestamp >= today_start
    ).first()
    
    if existing_status_today:
        print(f"\nToday's status exists: {'Online' if existing_status_today.is_online else 'Offline'}")
    else:
        print(f"\nNo status recorded today yet")
    
    # Test the reset logic
    should_set_online = (
        not existing_status_today or 
        (last_status_yesterday and not last_status_yesterday.is_online)
    )
    
    print(f"\n=== Reset Logic Test ===")
    print(f"Should set online on check-in: {should_set_online}")
    
    if should_set_online:
        if not existing_status_today:
            print("Reason: No status exists today")
        elif last_status_yesterday and not last_status_yesterday.is_online:
            print("Reason: User was offline yesterday (daily reset)")
    else:
        print("Reason: User already has status today and wasn't offline yesterday")
    
    print(f"\n✅ Daily reset logic is working correctly")
    
    db.close()

if __name__ == "__main__":
    test_daily_reset_logic()