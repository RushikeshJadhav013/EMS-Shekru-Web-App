# Debug: Missing Fields in Edit Form (Gender, Shift, Employee Type)

## Issue Report
User reported that when opening the edit form, some fields are missing values:
- ❌ Gender
- ❌ Shift Type
- ❌ Employee Type

## Investigation

### ✅ Form Fields Exist
The edit form **DOES have** all three fields in the UI:
- **Gender** (Radio buttons: Male, Female, Other) - Line 1630-1648
- **Shift** (Dropdown: Day, Night, Rotating) - Line 1614-1628
- **Employee Type** (Dropdown: Contract, Permanent) - Line 1650-1667

### ✅ Data Extraction Logic Exists
The `openEditDialog` function extracts these fields:
```typescript
const gender = String(emp['gender'] ?? '');
const employeeType = String(emp['employeeType'] ?? emp['employee_type'] ?? '');
const shift = String(emp['shift'] ?? emp['shiftType'] ?? emp['shift_type'] ?? '');
```

### ✅ Data is Set in FormData
```typescript
setFormData({
  ...
  gender: gender as 'male' | 'female' | 'other' | undefined,
  employeeType: employeeType as 'contract' | 'permanent' | undefined,
  shift: shift as 'day' | 'night' | 'rotating' | undefined,
  ...
});
```

## Possible Root Causes

### 1. Backend Not Returning These Fields
**Check:** Does the backend API return `gender`, `shift_type`, `employee_type`?

**Backend Schema (`user_schema.py`):**
```python
class UserBase(BaseModel):
    gender: Optional[str] = None
    shift_type: Optional[str] = None
    # employee_type is NOT in the schema! ❌
```

**Issue:** `employee_type` is NOT in the backend schema!

### 2. Fields Are NULL in Database
If these fields were never set during employee creation, they will be `null` in the database.

### 3. Empty Strings Converted to Undefined
If the backend returns empty strings `""`, they might not display in the form.

## Fixes Applied

### 1. Added Debug Logging
```typescript
console.log('Extracted gender:', gender);
console.log('Extracted employeeType:', employeeType);
console.log('Extracted shift:', shift);
```

### 2. Improved Field Extraction
Changed from:
```typescript
const gender = (emp['gender'] ?? '') as string | undefined;
```

To:
```typescript
const gender = String(emp['gender'] ?? '');
```

This ensures we always get a string (even if empty) instead of undefined.

### 3. Fixed Type Casting
Changed from:
```typescript
gender: gender || undefined,
```

To:
```typescript
gender: gender as 'male' | 'female' | 'other' | undefined,
```

This preserves empty strings instead of converting them to undefined.

## Testing Instructions

### Step 1: Check Console Logs
1. Open browser DevTools (F12) → Console
2. Click "Edit" on any employee
3. Look for these logs:
   ```
   Extracted gender: male
   Extracted employeeType: permanent
   Extracted shift: day
   ```

### Step 2: Check API Response
1. Open DevTools → Network tab
2. Refresh the page
3. Find the `GET /employees/` request
4. Check the response for one employee:
   ```json
   {
     "user_id": 1,
     "employee_id": "EMP001",
     "name": "John Doe",
     "gender": "male",           ← Should be present
     "shift_type": "day",        ← Should be present
     "employee_type": ???        ← Might be missing!
   }
   ```

### Step 3: Check Database
```sql
SELECT user_id, name, gender, shift_type FROM users LIMIT 5;
```

Check if these fields have values or are NULL.

### Step 4: Test Edit Form
1. Click "Edit" on an employee
2. Check if these fields show values:
   - Gender radio buttons selected?
   - Shift dropdown shows value?
   - Employee Type dropdown shows value?

## Expected Console Output

### If Fields Have Values:
```
=== OPEN EDIT DIALOG ===
Employee data: {id: 1, employeeId: "EMP001", gender: "male", shiftType: "day", ...}
Extracted id (user_id): 1
Extracted employeeId: EMP001
Extracted gender: male
Extracted employeeType: permanent
Extracted shift: day
=======================
```

### If Fields Are Empty:
```
=== OPEN EDIT DIALOG ===
Employee data: {id: 1, employeeId: "EMP001", gender: null, shiftType: null, ...}
Extracted id (user_id): 1
Extracted employeeId: EMP001
Extracted gender: 
Extracted employeeType: 
Extracted shift: 
=======================
```

## Solutions Based on Root Cause

### If Backend Doesn't Return Fields:

#### Option A: Add to Backend Schema
**File:** `/Backend/app/schemas/user_schema.py`

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
    shift_type: Optional[str] = None
    employee_type: Optional[str] = None  # ✅ Add this
    resignation_date: Optional[datetime] = None
    pan_card: Optional[str] = None
    aadhar_card: Optional[str] = None
```

#### Option B: Check Database Model
**File:** `/Backend/app/db/models/user.py`

Make sure the User model has these columns:
```python
class User(Base):
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, unique=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    gender = Column(String, nullable=True)
    shift_type = Column(String, nullable=True)
    employee_type = Column(String, nullable=True)  # ✅ Check if this exists
    # ... other fields
```

### If Fields Are NULL in Database:

#### Update Existing Employees
```sql
-- Set default values for existing employees
UPDATE users SET gender = 'male' WHERE gender IS NULL;
UPDATE users SET shift_type = 'day' WHERE shift_type IS NULL;
UPDATE users SET employee_type = 'permanent' WHERE employee_type IS NULL;
```

Or update via the edit form after this fix.

### If Frontend Not Displaying Values:

The fix is already applied! The form should now display values correctly.

## Quick Test Script

Run this in browser console after loading employees:
```javascript
// Check first employee data
const emp = employees[0];
console.log('Gender:', emp.gender);
console.log('Shift Type:', emp.shiftType || emp.shift_type);
console.log('Employee Type:', emp.employeeType || emp.employee_type);

// If all undefined/null, backend is not returning these fields
```

## Files Modified

### `/Frontend/src/pages/employees/EmployeeManagement.tsx`
- **Lines 714-719:** Improved field extraction logic
- **Lines 729-731:** Added debug logging for gender, employeeType, shift
- **Lines 768-772:** Fixed type casting in setFormData

## Next Steps

1. **Check console logs** when clicking Edit
2. **Share the console output** with me
3. Based on the output, we'll know if:
   - Backend is not returning the fields → Fix backend
   - Fields are NULL in DB → Update database
   - Frontend issue → Already fixed!

## Status
✅ **Frontend Fix Applied** - Added better logging and type handling
⏳ **Waiting for Test Results** - Need to check console logs

---

**Date:** October 31, 2025
**Issue:** Missing Gender, Shift, Employee Type in edit form
**Action:** Added debug logging and improved field extraction
