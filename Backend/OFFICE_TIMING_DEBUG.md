# Office Timing Status Calculation - Debug Guide

## Expected Behavior
- **Check-in time**: 10:00 AM
- **Check-in buffer**: 15 minutes
- **Late threshold**: 10:15 AM (anyone checking in after this is LATE)
- **Check-out time**: 7:00 PM (19:00)
- **Check-out buffer**: 10 minutes  
- **Early threshold**: 6:50 PM (18:50) (anyone checking out before this is EARLY)

## How It Works

### Backend Logic (`attendance_routes.py`)

1. **Fetch Office Timing**: `_resolve_office_timing(db, department, cache)`
   - First checks for department-specific timing
   - Falls back to global timing (where `department` is NULL or empty)

2. **Evaluate Status**: `_evaluate_attendance_status(check_in, check_out, timing)`
   - Converts check-in/check-out to IST timezone
   - Compares with office timing + grace period
   - Returns status: "on_time", "late", "early"

### Status Calculation

```python
# For Check-in
start_dt = datetime.combine(check_in_date, timing.start_time, tzinfo=INDIA_TZ)
start_dt += timedelta(minutes=timing.check_in_grace_minutes)  # Add buffer

if local_check_in > start_dt:
    check_in_status = "late"  # Checked in after 10:15 AM
else:
    check_in_status = "on_time"  # Checked in before or at 10:15 AM

# For Check-out
end_dt = datetime.combine(check_out_date, timing.end_time, tzinfo=INDIA_TZ)
end_dt -= timedelta(minutes=timing.check_out_grace_minutes)  # Subtract buffer

if local_check_out < end_dt:
    check_out_status = "early"  # Checked out before 6:50 PM
else:
    check_out_status = "on_time"  # Checked out after or at 6:50 PM
```

## Troubleshooting Steps

### 1. Check if Office Timing Exists in Database

```sql
SELECT * FROM office_timings WHERE is_active = TRUE;
```

Expected result:
```
id | department | start_time | end_time | check_in_grace_minutes | check_out_grace_minutes | is_active
---|------------|------------|----------|------------------------|-------------------------|----------
1  | NULL       | 10:00:00   | 19:00:00 | 15                     | 10                      | TRUE
```

### 2. Check User's Department

```sql
SELECT user_id, name, department FROM users WHERE user_id = <USER_ID>;
```

Make sure the department matches the office timing (or is NULL for global timing).

### 3. Check Attendance Record

```sql
SELECT 
    attendance_id,
    user_id,
    check_in,
    check_out,
    DATE(check_in) as check_in_date,
    TIME(check_in) as check_in_time
FROM attendance 
WHERE user_id = <USER_ID> 
ORDER BY check_in DESC 
LIMIT 5;
```

### 4. Verify Timezone Conversion

The backend stores times in UTC and converts to IST for comparison:
- UTC time is stored in database
- Converted to IST (UTC + 5:30) for comparison
- Example: 04:30 UTC = 10:00 IST

### 5. Test with API

```bash
# Get today's attendance
curl http://172.105.56.142/attendance/today

# Check office hours
curl http://172.105.56.142/attendance/office-hours
```

## Common Issues

### Issue 1: Always Shows "on-time"
**Cause**: No office timing configured in database
**Solution**: Set office timing via Admin Dashboard → Office Hours tab

### Issue 2: Wrong Status Despite Correct Timing
**Cause**: Department mismatch or timezone issue
**Solution**: 
- Verify user's department matches office timing
- Check if `is_active = TRUE` in office_timings table
- Verify check-in time is stored in UTC

### Issue 3: Status Not Updating in Dashboard
**Cause**: Frontend caching or backend not recalculating
**Solution**: 
- Refresh the page
- Check browser console for API errors
- Verify backend is returning correct `checkInStatus` and `checkOutStatus`

## Example Scenarios

### Scenario 1: On-time Check-in
- Office time: 10:00 AM + 15 min buffer = 10:15 AM
- User checks in: 10:10 AM
- **Expected**: Status = "on_time" ✓

### Scenario 2: Late Check-in
- Office time: 10:00 AM + 15 min buffer = 10:15 AM
- User checks in: 10:20 AM
- **Expected**: Status = "late" ✓

### Scenario 3: Early Check-out
- Office time: 7:00 PM - 10 min buffer = 6:50 PM
- User checks out: 6:45 PM
- **Expected**: Status = "early" ✓

### Scenario 4: On-time Check-out
- Office time: 7:00 PM - 10 min buffer = 6:50 PM
- User checks out: 7:05 PM
- **Expected**: Status = "on_time" ✓

## Files to Check

1. **Backend**: `Backend/app/routes/attendance_routes.py`
   - `_resolve_office_timing()` - Fetches office timing
   - `_evaluate_attendance_status()` - Calculates status
   - `_to_local_timezone()` - Converts UTC to IST

2. **Frontend**: 
   - `Frontend/src/pages/admin/AdminDashboard.tsx` - Recent activities
   - `Frontend/src/pages/attendance/AttendanceManager.tsx` - Attendance table
   - `Frontend/src/pages/attendance/AttendancePage.tsx` - User attendance

3. **Database**: 
   - `office_timings` table
   - `attendance` table
   - `users` table
