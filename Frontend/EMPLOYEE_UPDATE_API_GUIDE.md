# Employee Update API Integration Guide

## Overview
The employee update functionality has been migrated from using `employee_id` to `user_id` as the primary identifier.

## API Endpoint

### Update Employee
**Endpoint:** `PUT http://127.0.0.1:8000/employees/{user_id}`

**Path Parameters:**
- `user_id` (integer, required): The unique user ID (not employee_id)

**Request Body (JSON):**
```json
{
  "name": "string",
  "email": "user@example.com",
  "employee_id": "string",
  "department": "string",
  "designation": "string",
  "phone": "string",
  "address": "string",
  "role": "Employee",
  "gender": "string",
  "resignation_date": "2025-10-31T10:34:30.654Z",
  "pan_card": "string",
  "aadhar_card": "string",
  "shift_type": "string",
  "is_verified": true,
  "profile_photo": "string",
  "created_at": "2025-10-31T10:34:30.654Z"
}
```

**Success Response (200):**
```json
{
  "user_id": 1,
  "name": "John Doe",
  "email": "john@example.com",
  "employee_id": "EMP001",
  "department": "Engineering",
  "designation": "Senior Developer",
  "phone": "+91-9876543210",
  "address": "123 Main St",
  "role": "employee",
  "gender": "male",
  "resignation_date": null,
  "pan_card": "ABCDE1234F",
  "aadhar_card": "1234-5678-9012",
  "shift_type": "day",
  "is_verified": true,
  "profile_photo": null,
  "created_at": "2025-01-01T00:00:00.000Z"
}
```

**Error Response (404):**
```json
{
  "detail": "Employee not found"
}
```

## Frontend Implementation

### Files Modified:

#### 1. `/Frontend/src/lib/api.ts`
**Changes:**
- Updated `updateEmployee()` method to use `user_id` instead of `employee_id`
- Changed from FormData to JSON request body
- Updated endpoint from `/employees/{employee_id}/update` to `/employees/{user_id}`
- Added new fields: `is_verified`, `created_at`, `user_id`

**Updated Method Signature:**
```typescript
async updateEmployee(userId: string, employeeData: Partial<EmployeeData>): Promise<Employee>
```

**Key Changes:**
- **Old:** `PUT /employees/${employeeId}/update` with FormData
- **New:** `PUT /employees/${userId}` with JSON body

#### 2. `/Frontend/src/pages/employees/EmployeeManagement.tsx`
**Changes:**
- Updated `handleUpdateEmployee()` to use `user_id` (stored in `id` field)
- Changed from `employeeIdToUpdate` to `userIdToUpdate`
- Updated employee list comparison from `employeeId` to `id`

**Key Changes:**
```typescript
// Old
const employeeIdToUpdate = formData.employeeId || '';
await apiService.updateEmployee(employeeIdToUpdate, employeeData);
setEmployees(employees.map(emp => emp.employeeId === employeeIdToUpdate ? mappedUpdated : emp));

// New
const userIdToUpdate = selectedEmployee?.id || formData.id || '';
await apiService.updateEmployee(userIdToUpdate, employeeData);
setEmployees(employees.map(emp => emp.id === userIdToUpdate ? mappedUpdated : emp));
```

## Data Flow

### Update Employee Flow:
```
1. User clicks "Edit" on an employee
   ↓
2. Employee data is loaded into form (including user_id in 'id' field)
   ↓
3. User modifies employee details
   ↓
4. User clicks "Update Employee"
   ↓
5. Frontend extracts user_id from selectedEmployee.id
   ↓
6. Frontend calls: PUT /employees/{user_id} with JSON body
   ↓
7. Backend validates and updates employee record
   ↓
8. Backend returns updated employee data
   ↓
9. Frontend updates the employee in the local state
   ↓
10. Success toast is displayed
```

## Important Notes

### 1. ID Field Mapping
- **Backend:** Uses `user_id` (integer) as primary key
- **Frontend:** Stores `user_id` in the `id` field (string)
- **Employee ID:** `employee_id` is a separate field (e.g., "EMP001")

### 2. Request Format Change
- **Old:** FormData (multipart/form-data)
- **New:** JSON (application/json)
- **Reason:** Backend expects JSON body, not FormData

### 3. Profile Photo Handling
- Profile photo upload is currently handled separately
- The `profile_photo` field in the update request accepts a string path
- File upload functionality may need separate implementation

### 4. Required Fields
The following fields are required in the request body:
- `name`
- `email`
- `employee_id`

Optional fields will be set to `null` if not provided.

## Testing the Integration

### 1. Start Backend Server
```bash
cd Backend
uvicorn app.main:app --reload
```

### 2. Start Frontend Server
```bash
cd Frontend
npm run dev
```

### 3. Test Update Flow
1. Navigate to Employee Management page
2. Click "Edit" on any employee
3. Modify employee details
4. Click "Update Employee"
5. Verify success toast appears
6. Check that employee details are updated in the list

### 4. Verify API Call
Open browser DevTools → Network tab:
- Method: `PUT`
- URL: `http://127.0.0.1:8000/employees/{user_id}`
- Request Headers: `Content-Type: application/json`
- Request Body: JSON object with employee data

## Error Handling

The implementation handles the following error scenarios:

1. **Employee Not Found (404):**
   - Shows error toast: "Employee not found"

2. **Validation Error (422):**
   - Shows error toast with validation details

3. **Network Error:**
   - Shows error toast: "Failed to update employee. Please try again."

4. **Server Error (500):**
   - Shows error toast with error message from backend

## TypeScript Types

### EmployeeData Interface
```typescript
interface EmployeeData {
  name: string;
  email: string;
  employee_id: string;
  department?: string;
  designation?: string;
  phone?: string;
  address?: string;
  role?: string;
  gender?: string;
  resignation_date?: string;
  pan_card?: string;
  aadhar_card?: string;
  shift_type?: string;
  profile_photo?: File | string;
  is_verified?: boolean;
  created_at?: string;
  user_id?: number;
}
```

## Backend Requirements

### Required Backend Endpoint
```python
@router.put("/{user_id}", response_model=UserOut)
def update_employee(
    user_id: int,
    user_data: UserCreate,
    db: Session = Depends(get_db),
    _: RoleEnum = Depends(require_roles([RoleEnum.ADMIN, RoleEnum.HR]))
):
    # Implementation
```

### CORS Configuration
Make sure CORS is enabled for your frontend origin:
```python
origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]
```

## Troubleshooting

### Issue: "Employee not found" error
**Solution:** 
- Verify that the `user_id` is being passed correctly
- Check that the employee exists in the database
- Ensure you're using `id` field, not `employeeId`

### Issue: 422 Unprocessable Entity
**Solution:**
- Check that all required fields are present in the request
- Verify email format is valid
- Ensure data types match backend expectations

### Issue: CORS error
**Solution:**
- Verify backend CORS configuration includes your frontend URL
- Restart backend server after CORS changes

### Issue: Profile photo not updating
**Solution:**
- Profile photo upload may require separate endpoint
- Check if backend accepts file uploads in the update endpoint
- Consider implementing separate file upload functionality

## Next Steps

1. ✅ Employee Update API - **COMPLETED**
2. ⏳ Profile Photo Upload - **PENDING**
3. ⏳ Employee Delete API - **TO BE UPDATED**
4. ⏳ Employee Create API - **TO BE VERIFIED**
5. ⏳ Employee List API - **TO BE VERIFIED**

## Support

For issues or questions:
- Check backend API documentation: `http://127.0.0.1:8000/docs`
- Review backend logs for detailed error messages
- Verify database connection and data integrity
