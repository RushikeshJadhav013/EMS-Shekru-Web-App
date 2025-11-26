# Troubleshooting: Employee Update Error

## Follow These Steps Exactly:

### Step 1: Test Backend API Directly
Open your browser and go to:
```
http://172.105.56.142/employees/
```

**Expected Response:**
```json
[
  {
    "user_id": 1,
    "employee_id": "EMP001",
    "name": "John Doe",
    "email": "john@example.com",
    ...
  }
]
```

**Check:**
- ✅ Is `user_id` present in the response?
- ✅ Is the array not empty?

If empty or error, your backend has no employees data!

### Step 2: Clear Browser Cache & Reload
1. Open DevTools (F12)
2. Right-click the refresh button
3. Select "Empty Cache and Hard Reload"
4. Or press: `Ctrl + Shift + R` (Windows/Linux) or `Cmd + Shift + R` (Mac)

### Step 3: Check Console Logs

1. Open browser DevTools (F12)
2. Go to Console tab
3. Clear console (trash icon)
4. Refresh the page

**You should see:**
```
Loaded employees: [{id: 1, userId: 1, employeeId: "EMP001", ...}, ...]
First employee structure: {id: 1, userId: 1, employeeId: "EMP001", ...}
```

**If you see an error instead:**
- Check if backend is running
- Check CORS configuration
- Check Network tab for failed requests

### Step 4: Test Edit Flow

1. Click "Edit" on any employee
2. Check console for:
```
=== OPEN EDIT DIALOG ===
Employee data: {id: 1, userId: 1, ...}
Extracted id (user_id): 1
Extracted employeeId: EMP001
=======================
```

**If `Extracted id (user_id)` shows empty string:**
- The employee object doesn't have `id`, `user_id`, or `userId` fields
- This means the `toCamelCase` function isn't working
- Or the backend isn't returning `user_id`

### Step 5: Try to Update

1. Modify some field in the edit dialog
2. Click "Update Employee"
3. Check console for:
```
=== UPDATE DEBUG ===
selectedEmployee: {id: 1, userId: 1, ...}
formData: {id: "1", employeeId: "EMP001", ...}
userIdToUpdate: 1
===================
Updating employee with user_id: 1
```

**If `userIdToUpdate` is empty:**
- Check the logs above it
- Both `selectedEmployee` and `formData` should have an `id` field

### Step 6: Check Network Tab

1. Open DevTools → Network tab
2. Try to update an employee
3. Look for a request to `/employees/`

**Check the URL:**
- ❌ BAD: `PUT http://localhost:8000/employees/` (missing ID)
- ✅ GOOD: `PUT http://localhost:8000/employees/1` (has ID)

**Check the Status:**
- 200 OK = Success!
- 405 Method Not Allowed = Missing ID in URL
- 404 Not Found = Employee doesn't exist
- 422 Unprocessable Entity = Invalid data

## Common Issues & Solutions

### Issue 1: Backend not returning data
**Symptom:** `/employees/` returns empty array `[]`
**Solution:** 
```bash
# Create some test employees first
# Or check your database
```

### Issue 2: Backend not running
**Symptom:** Network error, can't connect
**Solution:**
```bash
cd Backend
uvicorn app.main:app --reload
```

### Issue 3: CORS error
**Symptom:** "blocked by CORS policy"
**Solution:** Already fixed in `/Backend/app/main.py`

### Issue 4: `user_id` not in response
**Symptom:** Backend returns data but no `user_id` field
**Solution:** Check `/Backend/app/schemas/user_schema.py`
- Line 25 should have: `user_id: int`

### Issue 5: Page not refreshing
**Symptom:** Old code still running
**Solution:**
1. Stop frontend server (Ctrl+C)
2. Clear browser cache
3. Restart: `npm run dev`
4. Hard reload page

### Issue 6: `toCamelCase` not working
**Symptom:** Employee objects don't have `id` field after loading
**Solution:** Check line 54-57 in `EmployeeManagement.tsx`:
```typescript
if (key === 'user_id') {
  acc['id'] = obj[key];
}
```

## Quick Debug Commands

### Check if backend is running:
```bash
curl http://172.105.56.142/
```

### Check employees endpoint:
```bash
curl http://172.105.56.142/employees/
```

### Check specific employee:
```bash
curl http://172.105.56.142/employees/1
```

## What to Share if Still Broken

If still not working, share these console logs:

1. **On page load:**
   - "Loaded employees" log
   - "First employee structure" log

2. **When clicking Edit:**
   - "OPEN EDIT DIALOG" logs
   - "Extracted id" logs

3. **When clicking Update:**
   - "UPDATE DEBUG" logs
   - Network tab screenshot showing the PUT request

## Manual Override (Last Resort)

If nothing works, you can manually set the user_id. Add this to `handleUpdateEmployee`:

```typescript
// TEMPORARY HACK - Remove after debugging
const userIdToUpdate = selectedEmployee?.id 
  || formData.id 
  || prompt('Enter user_id:') // Manual input
  || '';
```

This will show a popup asking for the user_id. Not pretty, but will help test if the API itself works.

---

**Need Help?**
- Check all console logs
- Check Network tab
- Share screenshots of errors
- Verify backend is returning `user_id` field
