#!/usr/bin/env python3
"""
Quick test script to verify the export endpoint is working
"""
import requests
from datetime import datetime, timedelta

# Configuration
# BASE_URL = "http://localhost:8000"  # Change if your backend runs on different port
BASE_URL = "https://staffly.space"  # Uncomment for production

def test_export_endpoint():
    """Test the export endpoint"""
    
    print("🧪 Testing Export Endpoint")
    print("=" * 50)
    
    # Calculate date range (last month)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Test parameters
    params = {
        'format': 'csv',
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
    }
    
    print(f"\n📋 Test Parameters:")
    print(f"   Format: {params['format']}")
    print(f"   Start Date: {params['start_date']}")
    print(f"   End Date: {params['end_date']}")
    print(f"   URL: {BASE_URL}/reports/export")
    
    # Note: You'll need a valid token for this to work
    # Get token by logging in first
    print("\n⚠️  Note: This test requires a valid authentication token")
    print("   Please login first and update the token below")
    
    token = "YOUR_TOKEN_HERE"  # Replace with actual token
    
    if token == "YOUR_TOKEN_HERE":
        print("\n❌ Please update the token in this script first")
        print("   1. Login to the application")
        print("   2. Open browser console")
        print("   3. Run: localStorage.getItem('token')")
        print("   4. Copy the token and paste it in this script")
        return
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    try:
        print("\n🔄 Making request...")
        response = requests.get(
            f"{BASE_URL}/reports/export",
            params=params,
            headers=headers,
            timeout=30
        )
        
        print(f"\n📊 Response:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"   Content-Length: {response.headers.get('Content-Length', 'N/A')} bytes")
        
        if response.status_code == 200:
            print("\n✅ Export endpoint is working!")
            print(f"   File size: {len(response.content)} bytes")
            
            # Save the file
            filename = f"test_export_{params['format']}.{params['format']}"
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"   Saved to: {filename}")
            
        elif response.status_code == 404:
            print("\n❌ Endpoint not found (404)")
            print("   The backend server may need to be restarted")
            print("   Run: ./restart_backend.sh")
            
        elif response.status_code == 401:
            print("\n❌ Unauthorized (401)")
            print("   Token is invalid or expired")
            print("   Please get a new token")
            
        else:
            print(f"\n❌ Request failed")
            print(f"   Response: {response.text[:200]}")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Connection Error")
        print("   Backend server is not running")
        print("   Start it with: uvicorn app.main:app --reload")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


def check_backend_status():
    """Check if backend is running"""
    print("\n🔍 Checking Backend Status")
    print("=" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running")
            data = response.json()
            print(f"   Message: {data.get('message', 'N/A')}")
            return True
        else:
            print(f"⚠️  Backend returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Backend is not running")
        print(f"   Could not connect to {BASE_URL}")
        return False
    except Exception as e:
        print(f"❌ Error checking backend: {str(e)}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Export Endpoint Test Script")
    print("=" * 50)
    
    # Check backend status first
    if check_backend_status():
        test_export_endpoint()
    else:
        print("\n⚠️  Please start the backend server first")
        print("   cd Backend")
        print("   uvicorn app.main:app --reload")
    
    print("\n" + "=" * 50)
