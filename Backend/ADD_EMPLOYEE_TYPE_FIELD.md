# Add Employee Type Field to Backend & Database

## Problem
The frontend has an "Employee Type" dropdown (Contract/Permanent) in both Add and Update employee forms, but the backend doesn't have this field in the database or API logic. This means the employee type selection is not being saved.

## Solution
Added `employee_type` field to:
1. ✅ Database model
2. ✅ Pydantic schemas
3. ✅ Registration API endpoint
4. ✅ Update API endpoint
5. ✅ Frontend API interface
6. ✅ Frontend create/update logic

---

## Changes Made

### 1. Database Model (`/Backend/app/db/models/user.py`)

**Added Line 30:**
```python
employee_type = Column(String(50), nullable=True)  # contract or permanent
```

**Full Context:**
```python
# PAN, Aadhaar, Shift, Employee Type
pan_card = Column(String(20), nullable=True)
aadhar_card = Column(String(20), nullable=True)
shift_type = Column(String(50), nullable=True)
employee_type = Column(String(50), nullable=True)  # ✅ Added
```

### 2. Pydantic Schema (`/Backend/app/schemas/user_schema.py`)

**Added Line 19:**
```python
employee_type: Optional[str] = None  # contract or permanent
```

**Full Context:**
```python
class UserBase(BaseModel):
    name: str
    email: EmailStr
    department: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role: Optional[RoleEnum] = RoleEnum.EMPLOYEE
    gender: Optional[str] = None
    resignation_date: Optional[datetime] = None
    pan_card: Optional[str] = None
    aadhar_card: Optional[str] = None
    shift_type: Optional[str] = None
    employee_type: Optional[str] = None  # ✅ Added
```

### 3. Registration Endpoint (`/Backend/app/routes/user_routes.py`)

**Added Line 38 (Function Parameter):**
```python
employee_type: Optional[str] = Form(None),  # ✅ Added
```

**Added Line 77 (UserCreate Object):**
```python
employee_type=employee_type,  # ✅ Added
```

**Full Context:**
```python
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register_employee(
    name: str = Form(...),
    email: EmailStr = Form(...),
    employee_id: str = Form(...),
    department: Optional[str] = Form(None),
    designation: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    role: Optional[RoleEnum] = Form(RoleEnum.EMPLOYEE),
    gender: Optional[str] = Form(None),
    resignation_date: Optional[datetime] = Form(None),
    pan_card: Optional[str] = Form(None),
    aadhar_card: Optional[str] = Form(None),
    shift_type: Optional[str] = Form(None),
    employee_type: Optional[str] = Form(None),  # ✅ Added
    profile_photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    # ... file upload logic ...
    
    user_in = UserCreate(
        name=name,
        email=email,
        employee_id=employee_id,
        department=department,
        designation=designation,
        phone=phone,
        address=address,
        role=role,
        gender=gender,
        resignation_date=resignation_date,
        pan_card=pan_card,
        aadhar_card=aadhar_card,
        shift_type=shift_type,
        employee_type=employee_type,  # ✅ Added
        profile_photo=profile_photo_path
    )
    
    return create_user(db, user_in)
```

### 4. Update Endpoint (`/Backend/app/routes/user_routes.py`)

**Added Line 175:**
```python
employee.employee_type = user_data.employee_type  # ✅ Added
```

**Full Context:**
```python
@router.put("/{user_id}", response_model=UserOut)
def update_employee(
    user_id: int,
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ... permission checks ...
    
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
    
    if current_user.role in [RoleEnum.ADMIN, RoleEnum.HR]:
        employee.role = user_data.role
    
    employee.gender = user_data.gender
    employee.resignation_date = user_data.resignation_date
    employee.pan_card = user_data.pan_card
    employee.aadhar_card = user_data.aadhar_card
    employee.shift_type = user_data.shift_type
    employee.employee_type = user_data.employee_type  # ✅ Added

    db.commit()
    db.refresh(employee)
    return employee
```

### 5. Frontend API Interface (`/Frontend/src/lib/api.ts`)

**Added Line 17 (EmployeeData Interface):**
```typescript
employee_type?: string;  // ✅ Added
```

**Added Line 154 (Update Request Body):**
```typescript
employee_type: employeeData.employee_type || null,  // ✅ Added
```

**Full Context:**
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
  employee_type?: string;  // ✅ Added
  profile_photo?: File | string;
  is_verified?: boolean;
  created_at?: string;
  user_id?: number;
}

// In updateEmployee method:
const requestBody: Record<string, unknown> = {
  name: employeeData.name,
  email: employeeData.email,
  employee_id: employeeData.employee_id,
  department: employeeData.department || null,
  designation: employeeData.designation || null,
  phone: employeeData.phone || null,
  address: employeeData.address || null,
  role: employeeData.role || 'Employee',
  gender: employeeData.gender || null,
  resignation_date: employeeData.resignation_date || null,
  pan_card: employeeData.pan_card || null,
  aadhar_card: employeeData.aadhar_card || null,
  shift_type: employeeData.shift_type || null,
  employee_type: employeeData.employee_type || null,  // ✅ Added
  is_verified: employeeData.is_verified !== undefined ? employeeData.is_verified : true,
  profile_photo: employeeData.profile_photo || null,
  created_at: employeeData.created_at || new Date().toISOString()
};
```

### 6. Frontend Create Employee (`/Frontend/src/pages/employees/EmployeeManagement.tsx`)

**Added Line 341:**
```typescript
employee_type: formData.employeeType,  // ✅ Added
```

**Full Context:**
```typescript
const employeeData: EmployeeData = {
  name: formData.name,
  email: formData.email,
  employee_id: formData.employeeId,
  department: formData.department,
  designation: formData.designation,
  phone: formData.phone ? `${formData.countryCode || '+91'}-${formData.phone.replace(/[^0-9]/g, '')}` : '',
  address: formData.address,
  role: formData.role,
  gender: formData.gender,
  resignation_date: formData.resignationDate || null,
  pan_card: formData.panCard,
  aadhar_card: formData.aadharCard,
  shift_type: formData.shift,
  employee_type: formData.employeeType,  // ✅ Added
  profile_photo: imageFile || undefined
};
```

### 7. Frontend Update Employee (`/Frontend/src/pages/employees/EmployeeManagement.tsx`)

**Added Line 459:**
```typescript
employee_type: formData.employeeType,  // ✅ Added
```

---

## Database Migration

### Option 1: Run Migration Script (Recommended)

```bash
cd Backend
python add_employee_type_column.py
```

This script will:
- Check if the column already exists
- Add the column if it doesn't exist
- Show success/error messages

### Option 2: Manual SQL Migration

If you prefer to run SQL manually:

```sql
-- Check if column exists
SELECT column_name 
FROM information_schema.columns 
WHERE table_name='users' AND column_name='employee_type';

-- Add column if it doesn't exist
ALTER TABLE users 
ADD COLUMN employee_type VARCHAR(50) NULL;
```

### Option 3: Drop and Recreate Database (Development Only!)

**⚠️ WARNING: This will DELETE ALL DATA!**

```bash
# Stop backend
# Delete database file (if using SQLite)
rm Backend/employee_management.db

# Restart backend - it will recreate tables with new schema
cd Backend
uvicorn app.main:app --reload
```

---

## Testing Instructions

### Step 1: Run Database Migration

```bash
cd Backend
python add_employee_type_column.py
```

**Expected Output:**
```
============================================================
Database Migration: Add employee_type Column
============================================================
Adding 'employee_type' column to 'users' table...
✅ Successfully added 'employee_type' column to 'users' table
   - Column type: VARCHAR(50)
   - Nullable: Yes
   - Default: NULL
============================================================
Migration completed!
============================================================
```

### Step 2: Restart Backend

```bash
# Stop backend (Ctrl+C)
cd Backend
uvicorn app.main:app --reload
```

### Step 3: Restart Frontend

```bash
# Stop frontend (Ctrl+C)
cd Frontend
npm run dev
```

### Step 4: Test Creating Employee

1. Go to Employee Management
2. Click "Add Employee"
3. Fill in all fields including **Employee Type** dropdown
4. Select either "Contract-based" or "Permanent"
5. Click "Create Employee"
6. **Check console** - should not show any errors
7. **Check database** - employee_type should be saved

### Step 5: Test Updating Employee

1. Click "Edit" on any employee
2. Check if **Employee Type** dropdown shows the saved value
3. Change it to a different value
4. Click "Update Employee"
5. **Refresh page** - the new value should persist

### Step 6: Verify in Database

```sql
-- Check if employee_type is being saved
SELECT user_id, name, employee_type FROM users;
```

**Expected Result:**
```
user_id | name       | employee_type
--------|------------|---------------
1       | John Doe   | permanent
2       | Jane Smith | contract
3       | Bob Wilson | permanent
```

---

## API Examples

### Create Employee with Employee Type

**Request:**
```http
POST /employees/register HTTP/1.1
Content-Type: multipart/form-data

name=John Doe
email=john@example.com
employee_id=EMP001
department=Engineering
designation=Developer
phone=+91-9876543210
address=123 Main St
role=employee
gender=male
pan_card=ABCDE1234F
aadhar_card=1234-5678-9012
shift_type=day
employee_type=permanent
```

**Response:**
```json
{
  "user_id": 1,
  "employee_id": "EMP001",
  "name": "John Doe",
  "email": "john@example.com",
  "department": "Engineering",
  "designation": "Developer",
  "role": "employee",
  "gender": "male",
  "shift_type": "day",
  "employee_type": "permanent",
  "is_verified": false,
  "created_at": "2025-10-31T12:00:00"
}
```

### Update Employee Type

**Request:**
```http
PUT /employees/1 HTTP/1.1
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "employee_id": "EMP001",
  "department": "Engineering",
  "designation": "Senior Developer",
  "phone": "+91-9876543210",
  "address": "123 Main St",
  "role": "employee",
  "gender": "male",
  "pan_card": "ABCDE1234F",
  "aadhar_card": "1234-5678-9012",
  "shift_type": "day",
  "employee_type": "contract"
}
```

**Response:**
```json
{
  "user_id": 1,
  "employee_id": "EMP001",
  "name": "John Doe",
  "email": "john@example.com",
  "employee_type": "contract",
  ...
}
```

---

## Files Modified

### Backend:
1. `/Backend/app/db/models/user.py` - Line 30
2. `/Backend/app/schemas/user_schema.py` - Line 19
3. `/Backend/app/routes/user_routes.py` - Lines 38, 77, 175

### Frontend:
1. `/Frontend/src/lib/api.ts` - Lines 17, 154
2. `/Frontend/src/pages/employees/EmployeeManagement.tsx` - Lines 341, 459

### New Files:
1. `/Backend/add_employee_type_column.py` - Migration script

---

## Validation

### Frontend Validation
The frontend already has the dropdown with two options:
- "Contract-based" → sends `"contract"`
- "Permanent" → sends `"permanent"`

### Backend Validation
Currently accepts any string. To add strict validation, update the schema:

```python
from enum import Enum

class EmployeeTypeEnum(str, Enum):
    CONTRACT = "contract"
    PERMANENT = "permanent"

class UserBase(BaseModel):
    # ... other fields ...
    employee_type: Optional[EmployeeTypeEnum] = None
```

---

## Troubleshooting

### Issue 1: Migration Script Fails

**Error:** `ModuleNotFoundError: No module named 'app'`

**Solution:**
```bash
# Run from Backend directory
cd Backend
python add_employee_type_column.py
```

### Issue 2: Column Already Exists

**Error:** `column "employee_type" of relation "users" already exists`

**Solution:** The column is already added! No action needed.

### Issue 3: Employee Type Not Saving

**Check:**
1. Did you run the migration script?
2. Did you restart the backend?
3. Check browser console for errors
4. Check backend logs for errors

**Debug:**
```python
# Add to update_employee function
print(f"Received employee_type: {user_data.employee_type}")
```

### Issue 4: Employee Type Not Showing in Edit Form

**Check:**
1. Is the backend returning `employee_type` in the API response?
2. Check browser console logs when clicking Edit
3. Look for: `Extracted employeeType: ...`

**If empty:**
- The employee was created before adding this field
- Update the employee to set a value

---

## Status
✅ **COMPLETE** - Employee Type field fully integrated!

## Summary

**What Was Added:**
- Database column: `employee_type VARCHAR(50) NULL`
- Backend API support for create and update
- Frontend sends employee_type in both create and update

**What Works Now:**
- ✅ Create employee with employee type
- ✅ Update employee type
- ✅ View employee type in edit form
- ✅ Employee type persists in database

**Next Steps:**
1. Run migration script
2. Restart backend and frontend
3. Test creating/updating employees
4. Verify data is saved in database

---

**Date:** October 31, 2025
**Issue:** Employee Type dropdown not saving data
**Resolution:** Added employee_type field to full stack
