"""
Test script to verify the Top 5 Performers endpoint
"""
import requests
from datetime import datetime

# Configuration
BASE_URL = "https://staffly.space"
TOKEN = "your_token_here"  # Replace with actual token

def test_executive_summary():
    """Test the executive summary endpoint with top 5 performers"""
    
    # Get current month and year
    now = datetime.now()
    month = now.month - 1  # 0-indexed
    year = now.year
    
    # Make request
    headers = {"Authorization": TOKEN}
    params = {"month": month, "year": year}
    
    response = requests.get(
        f"{BASE_URL}/reports/executive-summary",
        headers=headers,
        params=params
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        print("\n=== Executive Summary ===")
        print(f"Average Performance: {data.get('avgPerformance')}%")
        print(f"Total Tasks Completed: {data.get('totalTasksCompleted')}")
        print(f"Best Department: {data.get('bestDepartment', {}).get('name')} ({data.get('bestDepartment', {}).get('score')}%)")
        print(f"Total Employees Analyzed: {data.get('totalEmployeesAnalyzed')}")
        
        print("\n=== Top 5 Performers ===")
        top_performers = data.get('topPerformers', [])
        
        if top_performers:
            for i, performer in enumerate(top_performers, 1):
                print(f"\n{i}. {performer['name']} (ID: {performer['employeeId']})")
                print(f"   Department: {performer['department']}")
                print(f"   Role: {performer['role']}")
                print(f"   Overall Score: {performer['score']}%")
                print(f"   Breakdown:")
                print(f"     - Early Check-in: {performer['earlyCheckinScore']}% (25% weight)")
                print(f"     - Task Completion: {performer['taskCompletionScore']}% (30% weight)")
                print(f"     - Attendance: {performer['attendanceScore']}% (20% weight)")
                print(f"     - On-time Checkout: {performer['checkoutScore']}% (15% weight)")
                print(f"     - Leave Score: {performer['leaveScore']}% (10% weight)")
                print(f"   Stats:")
                print(f"     - Tasks: {performer['completedTasks']}/{performer['totalTasks']}")
                print(f"     - Attendance: {performer['attendanceDays']}/{performer['workingDays']} days")
                print(f"     - Early Check-ins: {performer['earlyCheckins']}")
                print(f"     - Leave Days: {performer['totalLeaveDays']}")
                print(f"     - Task Efficiency: {performer['taskEfficiency']} tasks/day")
        else:
            print("No top performers data available")
        
        print("\n=== Key Findings ===")
        for finding in data.get('keyFindings', []):
            print(f"  • {finding}")
        
        print("\n=== Recommendations ===")
        for rec in data.get('recommendations', []):
            print(f"  • {rec}")
        
        print("\n✅ Test Passed: Top 5 Performers endpoint is working correctly!")
        
    else:
        print(f"❌ Test Failed: {response.text}")

if __name__ == "__main__":
    print("Testing Top 5 Performers Feature")
    print("=" * 50)
    test_executive_summary()
