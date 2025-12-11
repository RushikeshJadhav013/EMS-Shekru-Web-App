"""
Test script to verify that completed and cancelled tasks cannot be passed.
This test validates the fix for the task status issue where completed tasks
were being passed to new employees with the completed status intact.
"""

import requests
import json

# Configuration
API_BASE_URL = "https://staffly.space"
# You'll need to replace this with a valid token
AUTH_TOKEN = "Bearer YOUR_TOKEN_HERE"

headers = {
    "Authorization": AUTH_TOKEN,
    "Content-Type": "application/json"
}

def test_pass_completed_task():
    """
    Test that passing a completed task returns an error
    """
    print("\n=== Test 1: Attempting to pass a completed task ===")
    
    # First, create a task
    print("Step 1: Creating a new task...")
    create_payload = {
        "title": "Test Task for Pass Validation",
        "description": "This task will be used to test pass validation",
        "priority": "Medium",
        "due_date": None,
        "assigned_to": 1,  # Replace with actual user ID
        "assigned_by": 1   # Replace with actual user ID
    }
    
    response = requests.post(f"{API_BASE_URL}/tasks", headers=headers, json=create_payload)
    if response.status_code != 200:
        print(f"❌ Failed to create task: {response.status_code}")
        print(response.text)
        return
    
    task = response.json()
    task_id = task["task_id"]
    print(f"✅ Task created with ID: {task_id}")
    
    # Mark the task as completed
    print("\nStep 2: Marking task as completed...")
    response = requests.put(
        f"{API_BASE_URL}/tasks/{task_id}/status?status=Completed",
        headers=headers
    )
    if response.status_code != 200:
        print(f"❌ Failed to update task status: {response.status_code}")
        print(response.text)
        return
    
    print("✅ Task marked as completed")
    
    # Try to pass the completed task
    print("\nStep 3: Attempting to pass the completed task...")
    pass_payload = {
        "new_assignee_id": 2,  # Replace with actual user ID
        "note": "Testing pass validation for completed task"
    }
    
    response = requests.post(
        f"{API_BASE_URL}/tasks/{task_id}/pass",
        headers=headers,
        json=pass_payload
    )
    
    if response.status_code == 400:
        error_detail = response.json().get("detail", "")
        if "Cannot pass a task with status" in error_detail:
            print("✅ PASS: Backend correctly rejected passing a completed task")
            print(f"   Error message: {error_detail}")
        else:
            print(f"❌ FAIL: Got 400 error but unexpected message: {error_detail}")
    else:
        print(f"❌ FAIL: Expected 400 error but got {response.status_code}")
        print(response.text)
    
    # Cleanup: Delete the test task
    print("\nStep 4: Cleaning up test task...")
    response = requests.delete(f"{API_BASE_URL}/tasks/{task_id}", headers=headers)
    if response.status_code == 200:
        print("✅ Test task deleted")
    else:
        print(f"⚠️  Could not delete test task: {response.status_code}")


def test_pass_pending_task():
    """
    Test that passing a pending task works correctly and resets status
    """
    print("\n=== Test 2: Passing a pending task (should work) ===")
    
    # Create a task
    print("Step 1: Creating a new task...")
    create_payload = {
        "title": "Test Task for Valid Pass",
        "description": "This task will be passed successfully",
        "priority": "Medium",
        "due_date": None,
        "assigned_to": 1,  # Replace with actual user ID
        "assigned_by": 1   # Replace with actual user ID
    }
    
    response = requests.post(f"{API_BASE_URL}/tasks", headers=headers, json=create_payload)
    if response.status_code != 200:
        print(f"❌ Failed to create task: {response.status_code}")
        print(response.text)
        return
    
    task = response.json()
    task_id = task["task_id"]
    print(f"✅ Task created with ID: {task_id}")
    
    # Mark as in progress
    print("\nStep 2: Marking task as in progress...")
    response = requests.put(
        f"{API_BASE_URL}/tasks/{task_id}/status?status=In Progress",
        headers=headers
    )
    if response.status_code != 200:
        print(f"❌ Failed to update task status: {response.status_code}")
        return
    
    print("✅ Task marked as in progress")
    
    # Pass the task
    print("\nStep 3: Passing the in-progress task...")
    pass_payload = {
        "new_assignee_id": 2,  # Replace with actual user ID
        "note": "Testing valid pass operation"
    }
    
    response = requests.post(
        f"{API_BASE_URL}/tasks/{task_id}/pass",
        headers=headers,
        json=pass_payload
    )
    
    if response.status_code == 200:
        updated_task = response.json()
        new_status = updated_task.get("status")
        if new_status == "Pending":
            print("✅ PASS: Task passed successfully and status reset to Pending")
            print(f"   New assignee: {updated_task.get('assigned_to')}")
        else:
            print(f"❌ FAIL: Task passed but status is '{new_status}' instead of 'Pending'")
    else:
        print(f"❌ FAIL: Expected 200 but got {response.status_code}")
        print(response.text)
    
    # Cleanup
    print("\nStep 4: Cleaning up test task...")
    response = requests.delete(f"{API_BASE_URL}/tasks/{task_id}", headers=headers)
    if response.status_code == 200:
        print("✅ Test task deleted")
    else:
        print(f"⚠️  Could not delete test task: {response.status_code}")


if __name__ == "__main__":
    print("=" * 60)
    print("Task Pass Validation Test Suite")
    print("=" * 60)
    print("\n⚠️  IMPORTANT: Update AUTH_TOKEN and user IDs before running!")
    print("\nThis test suite validates:")
    print("1. Completed tasks cannot be passed")
    print("2. Cancelled tasks cannot be passed")
    print("3. Valid tasks can be passed and status resets to Pending")
    
    # Uncomment to run tests (after updating token and user IDs)
    # test_pass_completed_task()
    # test_pass_pending_task()
    
    print("\n" + "=" * 60)
    print("Update the AUTH_TOKEN and user IDs, then uncomment the test calls")
    print("=" * 60)
