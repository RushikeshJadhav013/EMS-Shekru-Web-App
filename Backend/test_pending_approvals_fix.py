#!/usr/bin/env python3
"""
Test script to verify the pending approvals count fix
"""
import requests
import json
from datetime import datetime, date, timedelta

API_BASE_URL = "https://staffly.space"

def test_pending_approvals_consistency():
    """Test that dashboard pending count matches leave management page"""
    
    # You'll need to replace these with actual admin credentials
    admin_token = "your_admin_token_here"  # Replace with actual token
    
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }
    
    try:
        print("Testing Pending Approvals Consistency")
        print("=" * 50)
        
        # 1. Get admin dashboard data
        print("\n1. Fetching admin dashboard data...")
        dashboard_response = requests.get(f"{API_BASE_URL}/dashboard/admin", headers=headers)
        
        if dashboard_response.status_code == 200:
            dashboard_data = dashboard_response.json()
            dashboard_pending = dashboard_data.get('pendingLeaves', 0)
            print(f"   Dashboard pending approvals: {dashboard_pending}")
        else:
            print(f"   ❌ Dashboard API failed: {dashboard_response.status_code}")
            print(f"   Response: {dashboard_response.text}")
            return
        
        # 2. Get leave approvals inbox
        print("\n2. Fetching leave approvals inbox...")
        approvals_response = requests.get(f"{API_BASE_URL}/leave/approvals", headers=headers)
        
        if approvals_response.status_code == 200:
            approvals_data = approvals_response.json()
            approvals_count = len(approvals_data)
            print(f"   Leave management pending approvals: {approvals_count}")
            
            # Show details of pending approvals
            if approvals_data:
                print(f"\n   Pending approval details:")
                for approval in approvals_data:
                    print(f"   - {approval.get('name', 'Unknown')} ({approval.get('employee_id', 'N/A')})")
                    print(f"     Role: {approval.get('role', 'Unknown')}")
                    print(f"     Department: {approval.get('department', 'Unknown')}")
                    print(f"     Leave Type: {approval.get('leave_type', 'Unknown')}")
                    print(f"     Dates: {approval.get('start_date')} to {approval.get('end_date')}")
                    print()
            else:
                print("   No pending approvals found")
        else:
            print(f"   ❌ Approvals API failed: {approvals_response.status_code}")
            print(f"   Response: {approvals_response.text}")
            return
        
        # 3. Compare counts
        print("\n3. Comparing counts...")
        if dashboard_pending == approvals_count:
            print(f"   ✅ Counts match! Both show {dashboard_pending} pending approvals")
        else:
            print(f"   ❌ Counts don't match!")
            print(f"   Dashboard: {dashboard_pending}")
            print(f"   Leave Management: {approvals_count}")
            print(f"   Difference: {abs(dashboard_pending - approvals_count)}")
        
        # 4. Get all pending leaves for debugging
        print("\n4. Debugging - All pending leaves in system...")
        all_leaves_response = requests.get(f"{API_BASE_URL}/leave/", headers=headers)
        
        if all_leaves_response.status_code == 200:
            all_leaves = all_leaves_response.json()
            all_pending = [leave for leave in all_leaves if leave.get('status', '').lower() == 'pending']
            print(f"   Total pending leaves in system: {len(all_pending)}")
            
            if all_pending:
                print(f"   All pending leaves:")
                for leave in all_pending:
                    print(f"   - Leave ID: {leave.get('leave_id')}")
                    print(f"     User: {leave.get('name', 'Unknown')}")
                    print(f"     Status: {leave.get('status')}")
                    print()
        
    except Exception as e:
        print(f"❌ Error testing pending approvals: {e}")

def create_test_leave_requests():
    """Create some test leave requests for different roles"""
    
    print("\nCreating test leave requests...")
    print("Note: You'll need to implement this based on your user setup")
    print("Create leave requests from:")
    print("- HR users (should appear in admin dashboard)")
    print("- Manager users (should appear in admin dashboard)")
    print("- Employee users (should NOT appear in admin dashboard)")
    print("- Team Lead users (should NOT appear in admin dashboard)")

if __name__ == "__main__":
    print("Pending Approvals Consistency Test")
    print("=" * 50)
    
    print("\n⚠️  IMPORTANT: Update the admin_token variable with a valid admin token")
    print("You can get this by:")
    print("1. Login as admin through the frontend")
    print("2. Check browser developer tools -> Application -> Local Storage -> token")
    print("3. Copy the token value and update the script")
    
    # Uncomment the line below after updating the token
    # test_pending_approvals_consistency()
    
    create_test_leave_requests()
    
    print("\n✅ Test script ready. Update the token and uncomment the test call.")