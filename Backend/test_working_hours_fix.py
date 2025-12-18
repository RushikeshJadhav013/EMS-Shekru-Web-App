#!/usr/bin/env python3
"""
Test script to verify the working hours endpoint fix
"""

import requests
import jwt
from datetime import datetime, timedelta
import json

def test_working_hours_endpoint():
    """Test the working hours endpoint with proper authentication"""
    
    # Generate token with correct format
    secret = 'supersecretjwtkey'
    payload = {
        'sub': 'adityag23@gmail.com',  # Use email in sub field
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    
    # Test the endpoint
    try:
        response = requests.get(
            'https://staffly.space/attendance/working-hours/37',
            headers={'Authorization': f'Bearer {token}'}
        )
        
        print(f'Status Code: {response.status_code}')
        
        if response.status_code == 200:
            data = response.json()
            print('✅ Working hours endpoint is working!')
            print(f'Working Hours: {data["working_hours"]} hours')
            print(f'Total Seconds: {data["total_seconds"]} seconds')
            print(f'Currently Online: {data["is_currently_online"]}')
            print(f'Check In: {data["check_in"]}')
            print(f'Check Out: {data["check_out"]}')
            
            # Convert to minutes and seconds format
            total_seconds = data["total_seconds"]
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                time_display = f'{hours}:{minutes:02d}'
            else:
                time_display = f'{minutes}:{seconds:02d}'
                
            print(f'Formatted Time: {time_display}')
            
        else:
            print(f'❌ Error: {response.text}')
            
    except Exception as e:
        print(f'❌ Error: {e}')

if __name__ == '__main__':
    test_working_hours_endpoint()