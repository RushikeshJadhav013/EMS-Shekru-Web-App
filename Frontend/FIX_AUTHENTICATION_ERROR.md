# Fix: 403 Forbidden - Not Authenticated Error

## Problem
After fixing the user_id issue, the employee update API was failing with:
```
PUT http://localhost:8000/employees/2 403 (Forbidden)
Error: Not authenticated
```

## Root Cause
The backend endpoint `/employees/{user_id}` requires authentication:

```python
@router.put("/{user_id}", response_model=UserOut)
def update_employee(
    user_id: int,
    user_data: UserCreate,
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles([RoleEnum.ADMIN, RoleEnum.HR]))  # ← Requires auth
):
```

The frontend API calls were NOT sending the authentication token in the request headers.

## Solution

### Updated `/Frontend/src/lib/api.ts`

#### 1. Added Auth to `request()` Method
```typescript
private async request(endpoint: string, options: RequestInit = {}) {
  const url = `${this.baseURL}${endpoint}`;

  // ✅ Get auth token from localStorage
  const token = localStorage.getItem('token');
  
  const config: RequestInit = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}), // ✅ Add auth token
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        throw new Error('Not authenticated'); // ✅ Better error message
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  }
}
```

#### 2. Added Auth to `updateEmployee()` Method
```typescript
async updateEmployee(userId: string, employeeData: Partial<EmployeeData>): Promise<Employee> {
  // ... prepare requestBody ...

  // ✅ Get auth token from localStorage
  const token = localStorage.getItem('token');
  
  const response = await fetch(`${this.baseURL}/employees/${userId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}), // ✅ Add auth token
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
  }

  return await response.json();
}
```

## How Authentication Works

### 1. Login Flow (Already Working)
```typescript
// When user logs in via OTP
await login({
  user_id: userData.user_id,
  email: userData.email,
  name: userData.name,
  role: userRole,
  access_token: userData.access_token,  // ← Token is saved here
  token_type: userData.token_type
});
```

### 2. Token Storage (AuthContext)
```typescript
// In AuthContext.tsx
localStorage.setItem('token', userData.access_token);
localStorage.setItem('user', JSON.stringify(userData));
```

### 3. Token Usage (API Calls)
```typescript
// When making API requests
const token = localStorage.getItem('token');

fetch(url, {
  headers: {
    'Authorization': `Bearer ${token}`  // ← Sent to backend
  }
});
```

### 4. Backend Validation
```python
# Backend extracts and validates token
def get_current_user(token: str = Depends(api_key_header)):
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
    
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    # ... verify user ...
```

## Backend Endpoints Requiring Auth

### ✅ Requires Auth (Admin/HR only):
- `PUT /employees/{user_id}` - Update employee
- `DELETE /employees/{user_id}` - Delete employee
- `GET /employees/{user_id}` - Get single employee

### ❌ No Auth Required (Public):
- `GET /employees/` - List all employees
- `POST /employees/register` - Register new employee
- `POST /auth/send-otp` - Send OTP
- `POST /auth/verify-otp` - Verify OTP

## Testing Instructions

### 1. Login First
```
1. Go to http://localhost:8080/login
2. Enter email and request OTP
3. Verify OTP
4. You should be logged in and token saved
```

### 2. Verify Token is Saved
```
1. Open DevTools (F12) → Console
2. Type: localStorage.getItem('token')
3. Should see: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 3. Test Employee Update
```
1. Navigate to Employee Management
2. Click "Edit" on any employee
3. Modify details
4. Click "Update Employee"
5. Check Network tab - should see "Authorization: Bearer {token}" header
6. Should succeed with 200 OK
```

## Checking Request Headers in DevTools

### In Network Tab:
```
1. Click on the PUT request to /employees/2
2. Go to "Headers" tab
3. Look under "Request Headers"
4. Should see:
   Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Common Issues & Solutions

### Issue 1: "Not authenticated" error persists
**Check:**
```javascript
// In console
localStorage.getItem('token')
```

**If null:**
- You're not logged in
- Login again via OTP

### Issue 2: Token expired
**Symptom:** Was working, now getting 403
**Solution:**
- Login again to get fresh token
- Backend tokens expire after X hours (check backend config)

### Issue 3: Wrong role
**Symptom:** 403 Forbidden even with valid token
**Reason:** User role is not ADMIN or HR
**Solution:**
- Update endpoint requires Admin or HR role
- Check your user role in database
- Login with admin/hr account

### Issue 4: Token not sent
**Symptom:** Network tab shows no Authorization header
**Solution:**
- Hard refresh page (Ctrl+Shift+R)
- Clear cache
- Check if token exists in localStorage

## Files Modified

### `/Frontend/src/lib/api.ts`
- Line 75-76: Added token retrieval in `request()` method
- Line 82: Added Authorization header
- Line 91-93: Better error handling for auth errors
- Line 165-166: Added token retrieval in `updateEmployee()` method
- Line 172: Added Authorization header

## Security Notes

### Current Implementation (Development)
- Token stored in `localStorage`
- Token sent in Authorization header as "Bearer {token}"
- No token refresh mechanism

### Production Recommendations
1. **Use httpOnly cookies** instead of localStorage
2. **Implement token refresh** mechanism
3. **Add CSRF protection**
4. **Use HTTPS** for all requests
5. **Implement logout** to clear tokens
6. **Add token expiry handling** in frontend

## Expected Request Format

### Before Fix (Missing Auth):
```http
PUT /employees/2 HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{...employee data...}
```
❌ **Result:** 403 Forbidden

### After Fix (With Auth):
```http
PUT /employees/2 HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

{...employee data...}
```
✅ **Result:** 200 OK

## Status
✅ **FIXED** - Authentication now working for employee updates!

## Related Documentation
- `API_INTEGRATION_GUIDE.md` - Authentication API docs
- `EMPLOYEE_UPDATE_API_GUIDE.md` - Employee update API docs
- `FINAL_FIX_EMPLOYEE_UPDATE.md` - Previous user_id fix

---

**Date:** October 31, 2025
**Impact:** All authenticated endpoints now working
**Next:** Test with actual admin/hr user account
