#!/usr/bin/env python3
"""
Debug script to test attendance API endpoint via HTTP request to identify the real 500 error
"""

import sys
import os
import requests
import json
from datetime import datetime, timedelta

# Add the Backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_attendance_http():
    """Test the attendance API endpoint via HTTP to see the real error"""
    
    try:
        print("🔧 Testing Attendance API via HTTP...")
        
        # Test the endpoint that's failing
        base_url = "https://staffly.space"
        endpoint = f"{base_url}/attendance/my-attendance/2"
        
        print(f"📝 Testing endpoint: {endpoint}")
        
        # Make the HTTP request
        try:
            response = requests.get(endpoint, timeout=10)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Request successful!")
                data = response.json()
                print(f"Response: {len(data)} records returned")
                return True
            elif response.status_code == 500:
                print("❌ 500 Internal Server Error - this is the issue!")
                print("Response text:", response.text)
                
                # Try to parse error details
                try:
                    error_data = response.json()
                    print("Error details:", json.dumps(error_data, indent=2))
                except:
                    print("Could not parse error response as JSON")
                
                return False
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                print("Response:", response.text)
                return False
                
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to backend server")
            print("💡 Make sure the backend is running on port 8000")
            print("   cd Backend && uvicorn app.main:app --reload")
            return False
        except requests.exceptions.Timeout:
            print("❌ Request timed out")
            return False
        except Exception as req_error:
            print(f"❌ Request failed: {req_error}")
            return False
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_backend_logs():
    """Check if we can get more details from backend logs"""
    print("\n🔍 Checking for backend logs...")
    
    # Check if there's a log file
    log_files = [
        "Backend/backend.log",
        "backend.log",
        "app.log"
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            print(f"📋 Found log file: {log_file}")
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    # Get last 20 lines
                    recent_lines = lines[-20:] if len(lines) > 20 else lines
                    print("Recent log entries:")
                    for line in recent_lines:
                        if 'ERROR' in line or '500' in line or 'attendance' in line.lower():
                            print(f"  {line.strip()}")
            except Exception as e:
                print(f"Could not read log file: {e}")
        else:
            print(f"Log file not found: {log_file}")

def test_direct_function_call():
    """Test the function directly to compare with HTTP"""
    print("\n🔍 Testing function directly for comparison...")
    
    try:
        from app.db.database import SessionLocal
        from app.routes.attendance_routes import get_self_attendance
        
        db = SessionLocal()
        
        # Test with user ID 2 (same as HTTP request)
        result = get_self_attendance(2, db)
        print(f"✅ Direct function call worked: {len(result)} records")
        
        # Try to serialize the result to JSON to see if that's the issue
        try:
            json_result = json.dumps(result, default=str)
            print("✅ JSON serialization worked")
        except Exception as json_error:
            print(f"❌ JSON serialization failed: {json_error}")
            print("This might be the cause of the 500 error!")
            return False
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Direct function call failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Attendance API HTTP Debug Test")
    print("=" * 60)
    
    # Test HTTP request
    http_success = test_attendance_http()
    
    # Test direct function call
    direct_success = test_direct_function_call()
    
    # Check logs
    test_backend_logs()
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"HTTP Request: {'✅ SUCCESS' if http_success else '❌ FAILED'}")
    print(f"Direct Call: {'✅ SUCCESS' if direct_success else '❌ FAILED'}")
    
    if direct_success and not http_success:
        print("\n💡 DIAGNOSIS:")
        print("The function works directly but fails via HTTP.")
        print("This suggests the issue is in:")
        print("  1. FastAPI response serialization")
        print("  2. Pydantic model validation")
        print("  3. HTTP middleware or authentication")
        print("  4. JSON serialization of datetime objects")
    elif not direct_success:
        print("\n💡 DIAGNOSIS:")
        print("The function itself is failing.")
        print("Check the error details above for the root cause.")
    
    print("=" * 60)