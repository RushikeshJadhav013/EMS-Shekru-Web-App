"""
Test script to verify Top 5 Performers API endpoint
"""
import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8080"
# You'll need to replace this with a valid token
TOKEN = "your_token_here"

def test_executive_summary():
    """Test the executive summary endpoint"""
    
    # Get current month and year
    now = datetime.now()
    month = now.month - 1  # 0-indexed (0-11)
    year = now.year
    
    print(f"Testing Executive Summary API")
    print(f"Month: {month} (0-indexed), Year: {year}")
    print("-" * 50)
    
    # Make API request
    url = f"{BASE_URL}/reports/executive-summary"
    params = {
        "month": month,
        "year": year
    }
    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✅ API Response Successful")
            print(f"Total Employees Analyzed: {data.get('totalEmployeesAnalyzed', 0)}")
            print(f"Average Performance: {data.get('avgPerformance', 0)}%")
            print(f"Total Tasks Completed: {data.get('totalTasksCompleted', 0)}")
            
            top_performers = data.get('topPerformers', [])
            print(f"\n📊 Top Performers Count: {len(top_performers)}")
            
            if top_performers:
                print("\n🏆 Top 5 Performers:")
                print("-" * 80)
                for i, performer in enumerate(top_performers, 1):
                    print(f"\n{i}. {performer.get('name', 'N/A')}")
                    print(f"   Employee ID: {performer.get('employeeId', 'N/A')}")
                    print(f"   Department: {performer.get('department', 'N/A')}")
                    print(f"   Role: {performer.get('role', 'N/A')}")
                    print(f"   Overall Score: {performer.get('score', 0)}")
                    print(f"   Metrics:")
                    print(f"     - Early Check-in: {performer.get('earlyCheckinScore', 0)}%")
                    print(f"     - Task Completion: {performer.get('taskCompletionScore', 0)}%")
                    print(f"     - Attendance: {performer.get('attendanceScore', 0)}%")
                    print(f"     - On-time Checkout: {performer.get('checkoutScore', 0)}%")
                    print(f"     - Leave Score: {performer.get('leaveScore', 0)}%")
                    print(f"   Stats:")
                    print(f"     - Tasks: {performer.get('completedTasks', 0)}/{performer.get('totalTasks', 0)}")
                    print(f"     - Attendance: {performer.get('attendanceDays', 0)}/{performer.get('workingDays', 0)}")
                    print(f"     - Early Check-ins: {performer.get('earlyCheckins', 0)}")
                    print(f"     - Leave Days: {performer.get('totalLeaveDays', 0)}")
            else:
                print("\n⚠️ No top performers data available")
                print("This could mean:")
                print("  - No employees have attendance or task data for this month")
                print("  - All employees are being filtered out")
                
            # Print full response for debugging
            print("\n" + "=" * 80)
            print("Full API Response:")
            print(json.dumps(data, indent=2))
            
        else:
            print(f"\n❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


def test_with_different_months():
    """Test multiple months to find data"""
    print("\n" + "=" * 80)
    print("Testing Multiple Months")
    print("=" * 80)
    
    year = datetime.now().year
    
    for month in range(12):
        url = f"{BASE_URL}/reports/executive-summary"
        params = {"month": month, "year": year}
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        try:
            response = requests.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                top_performers = data.get('topPerformers', [])
                if top_performers:
                    month_name = datetime(year, month + 1, 1).strftime('%B')
                    print(f"\n✅ {month_name} {year}: {len(top_performers)} performers found")
        except:
            pass


if __name__ == "__main__":
    print("=" * 80)
    print("Top 5 Performers API Test")
    print("=" * 80)
    print("\nIMPORTANT: Update the TOKEN variable with a valid authentication token")
    print("You can get this from your browser's developer tools (Application > Local Storage)")
    print("\n")
    
    # Uncomment when you have a valid token
    # test_executive_summary()
    # test_with_different_months()
    
    print("\n⚠️ Please update TOKEN in the script and uncomment the test functions")
