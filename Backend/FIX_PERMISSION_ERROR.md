# Fix: 403 Forbidden - Operation Not Permitted

## Problem
When trying to update employee details, users were getting:
```
PUT http://localhost:8000/employees/2 403 (Forbidden)
{"detail": "Operation not permitted"}
```

This happened even when authenticated, because the endpoint required **Admin or HR role only**.

## Root Cause
The original endpoint had strict role-based access control:
```python
@router.put("/{user_id}", response_model=UserOut)
def update_employee(
    user_id: int,
    user_data: UserCreate,
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles([RoleEnum.ADMIN, RoleEnum.HR]))  # ❌ Too restrictive
):
```

**Problem:** Regular employees couldn't update their own profiles!

## Solution
Changed the permission logic to allow:
1. ✅ **Users can update their OWN profile**
2. ✅ **Admin/HR can update ANY profile**
3. ✅ **Only Admin/HR can change roles**

### Updated Code

#### `/Backend/app/routes/user_routes.py`

**Imports (Lines 7-9):**
```python
from app.dependencies import require_roles, get_current_user
from app.enums import RoleEnum
from app.db.models.user import User
```

**Updated Endpoint (Lines 136-175):**
```python
# ✅ Update employee details (Users can update their own profile, Admin/HR can update anyone)
@router.put("/{user_id}", response_model=UserOut)
def update_employee(
    user_id: int,
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ Get current logged-in user
):
    # Check permissions: User can update their own profile OR must be Admin/HR to update others
    if current_user.user_id != user_id and current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted. You can only update your own profile."
        )
    
    employee = get_user(db, user_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # Update fields
    employee.name = user_data.name
    employee.email = user_data.email
    employee.department = user_data.department
    employee.designation = user_data.designation
    employee.phone = user_data.phone
    employee.address = user_data.address
    
    # ✅ Only Admin/HR can change roles
    if current_user.role in [RoleEnum.ADMIN, RoleEnum.HR]:
        employee.role = user_data.role
    
    employee.gender = user_data.gender
    employee.resignation_date = user_data.resignation_date
    employee.pan_card = user_data.pan_card
    employee.aadhar_card = user_data.aadhar_card
    employee.shift_type = user_data.shift_type

    db.commit()
    db.refresh(employee)
    return employee
```

## Permission Logic Breakdown

### Scenario 1: User Updates Their Own Profile ✅
```
Current User: user_id=2, role=employee
Target: user_id=2

Check: current_user.user_id (2) == user_id (2)
Result: ALLOWED ✅
```

### Scenario 2: User Tries to Update Another User ❌
```
Current User: user_id=2, role=employee
Target: user_id=3

Check: current_user.user_id (2) != user_id (3) AND role != admin/hr
Result: FORBIDDEN ❌
Error: "Operation not permitted. You can only update your own profile."
```

### Scenario 3: Admin Updates Any User ✅
```
Current User: user_id=1, role=admin
Target: user_id=2

Check: current_user.user_id (1) != user_id (2) BUT role == admin
Result: ALLOWED ✅
```

### Scenario 4: HR Updates Any User ✅
```
Current User: user_id=5, role=hr
Target: user_id=2

Check: current_user.user_id (5) != user_id (2) BUT role == hr
Result: ALLOWED ✅
```

## Role Change Protection

### Regular User Tries to Change Role ❌
```python
if current_user.role in [RoleEnum.ADMIN, RoleEnum.HR]:
    employee.role = user_data.role  # Only executed for admin/hr
```

**Result:** Regular users can update their profile but NOT change their role.

### Admin/HR Changes Role ✅
```python
if current_user.role in [RoleEnum.ADMIN, RoleEnum.HR]:
    employee.role = user_data.role  # ✅ Executed
```

**Result:** Admin/HR can change any user's role.

## Testing Instructions

### Test 1: User Updates Own Profile
```bash
# Login as regular employee (user_id=2)
# Get token from login

curl -X PUT http://localhost:8000/employees/2 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Name",
    "email": "user@example.com",
    "employee_id": "EMP002",
    "department": "Engineering"
  }'

# Expected: 200 OK ✅
```

### Test 2: User Tries to Update Another User
```bash
# Login as regular employee (user_id=2)
# Try to update user_id=3

curl -X PUT http://localhost:8000/employees/3 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hacker Name",
    "email": "hacker@example.com",
    "employee_id": "EMP003"
  }'

# Expected: 403 Forbidden ❌
# Response: {"detail": "Operation not permitted. You can only update your own profile."}
```

### Test 3: Admin Updates Any User
```bash
# Login as admin (user_id=1)

curl -X PUT http://localhost:8000/employees/3 \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated by Admin",
    "email": "user3@example.com",
    "employee_id": "EMP003",
    "role": "hr"
  }'

# Expected: 200 OK ✅
# Role change allowed because admin
```

### Test 4: User Tries to Change Own Role
```bash
# Login as regular employee (user_id=2)

curl -X PUT http://localhost:8000/employees/2 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "employee_id": "EMP002",
    "role": "admin"  # ← Trying to become admin
  }'

# Expected: 200 OK (profile updated)
# BUT: Role remains unchanged (not admin) ✅
```

## Frontend Integration

The frontend doesn't need any changes! It will now work for all users:

1. **Regular employees** can update their own profile
2. **Admin/HR** can update any employee
3. No more "Operation not permitted" errors for self-updates

## Security Benefits

### ✅ What This Fixes:
1. Users can now update their own information
2. Users still can't update other users
3. Users can't escalate their own privileges
4. Admin/HR retain full control

### ✅ Security Maintained:
1. Authentication still required (JWT token)
2. Role-based access control for cross-user updates
3. Role changes protected (admin/hr only)
4. User can only modify their own data

## API Endpoint Summary

### `PUT /employees/{user_id}`

**Authentication:** Required (JWT token)

**Permissions:**
- ✅ User can update their own profile (`current_user.user_id == user_id`)
- ✅ Admin can update any profile
- ✅ HR can update any profile
- ❌ Regular user cannot update other users

**Role Changes:**
- ✅ Admin can change roles
- ✅ HR can change roles
- ❌ Regular users cannot change roles (even their own)

**Request:**
```http
PUT /employees/2 HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "employee_id": "EMP002",
  "department": "Engineering",
  "designation": "Senior Developer",
  "phone": "+91-1234567890",
  "address": "123 Main St",
  "role": "employee",
  "gender": "male",
  "pan_card": "ABCDE1234F",
  "aadhar_card": "123456789012",
  "shift_type": "day"
}
```

**Response (Success):**
```json
{
  "user_id": 2,
  "employee_id": "EMP002",
  "name": "John Doe",
  "email": "john@example.com",
  "department": "Engineering",
  "designation": "Senior Developer",
  "role": "employee",
  "is_verified": true,
  "created_at": "2025-10-31T12:00:00"
}
```

**Response (Forbidden):**
```json
{
  "detail": "Operation not permitted. You can only update your own profile."
}
```

## Files Modified

### `/Backend/app/routes/user_routes.py`
- **Line 7:** Added `get_current_user` import
- **Line 9:** Added `User` model import
- **Lines 136-175:** Updated `update_employee` endpoint with flexible permissions

## Migration Notes

### Before:
- Only Admin/HR could update ANY employee
- Regular employees couldn't update their own profile
- Very restrictive

### After:
- Admin/HR can still update ANY employee
- Regular employees can update THEIR OWN profile
- Role changes still protected
- More user-friendly

## Status
✅ **FIXED** - Users can now update their own profiles!

## Related Issues
- Fixes: "Operation not permitted" error for self-updates
- Maintains: Security for cross-user updates
- Maintains: Role change protection

---

**Date:** October 31, 2025
**Impact:** All authenticated users can now update their profiles
**Security:** Maintained - users still can't update others or change roles
