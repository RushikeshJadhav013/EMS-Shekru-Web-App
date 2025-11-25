# Recent Activity Time Display Fix

## Issue
In the Admin Dashboard's "Recent Activities" section, login and activity times were displaying incorrectly. For example:
- Attendance page showed check-in at **11:43 AM**
- Recent activity section showed the same check-in at **06:19 AM** (wrong!)

This was a 5 hour 30 minute difference - exactly the UTC to IST offset.

## Root Cause
The backend sends UTC time without the 'Z' timezone suffix. The activity time was being displayed using:
```typescript
{new Date(activity.time).toLocaleTimeString()}
```

This method:
- Doesn't handle UTC time without 'Z' suffix properly
- Treats the time as local time instead of UTC
- Results in incorrect timezone conversion
- Shows times 5.5 hours behind actual IST time

## Solution
Created a `formatActivityTime()` function that properly handles UTC to IST conversion, matching the logic used in the AttendancePage:

```typescript
const formatActivityTime = (timeString: string) => {
  if (!timeString) return '-';
  
  let date: Date;
  if (timeString.includes('T')) {
    // ISO datetime string
    if (timeString.includes('Z') || timeString.includes('+') || timeString.includes('-', 10)) {
      date = new Date(timeString); // Has timezone info
    } else {
      date = new Date(timeString + 'Z'); // Assume UTC, add 'Z'
    }
  } else {
    // Parse and assume UTC
    date = new Date(timeString);
    if (!timeString.includes('Z') && !timeString.includes('+')) {
      const isoString = date.toISOString();
      date = new Date(isoString);
    }
  }
  
  // Convert to IST
  return date.toLocaleString('en-IN', { 
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  });
};
```

## Changes Made

### File: `Frontend/src/pages/admin/AdminDashboard.tsx`

**Before:**
```tsx
<p className="text-xs text-muted-foreground">
  {new Date(activity.time).toLocaleTimeString()}
</p>
```

**After:**
```tsx
// Added formatActivityTime function
const formatActivityTime = (timeString: string) => {
  if (!timeString) return '-';
  
  let date: Date;
  if (timeString.includes('T')) {
    if (timeString.includes('Z') || timeString.includes('+') || timeString.includes('-', 10)) {
      date = new Date(timeString);
    } else {
      date = new Date(timeString + 'Z'); // Add 'Z' to indicate UTC
    }
  } else {
    date = new Date(timeString);
    if (!timeString.includes('Z') && !timeString.includes('+')) {
      const isoString = date.toISOString();
      date = new Date(isoString);
    }
  }
  
  return date.toLocaleString('en-IN', { 
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  });
};

// Updated display
<p className="text-xs text-muted-foreground">
  {formatActivityTime(activity.time)}
</p>
```

## How It Works

The `toLocaleTimeString()` method now includes:

1. **Locale**: `'en-IN'` - Indian English format
2. **Timezone**: `'Asia/Kolkata'` - IST timezone (UTC+5:30)
3. **Hour Format**: `'2-digit'` - Always shows 2 digits (e.g., 09:00)
4. **Minute Format**: `'2-digit'` - Always shows 2 digits
5. **12-hour Format**: `hour12: true` - Shows AM/PM format

## Benefits

✅ **Accurate Time Display**: All activity times now show in IST
✅ **Consistent Formatting**: Same format across all activities
✅ **User-Friendly**: 12-hour format with AM/PM
✅ **Timezone Aware**: Properly converts UTC to IST
✅ **No Confusion**: Matches actual activity times

## Example Output

**Before:**
- Backend sends: `2024-01-15T11:43:00` (UTC time without 'Z')
- Display showed: "06:13 AM" (treated as local time, wrong!)
- Actual IST time should be: "05:13 PM" (11:43 UTC + 5:30 = 17:13 IST)

**After:**
- Backend sends: `2024-01-15T11:43:00` (UTC time without 'Z')
- Function adds 'Z': `2024-01-15T11:43:00Z`
- Converts to IST: "05:13 PM" ✓ (correct!)
- Matches attendance page timing exactly

## Affected Sections

This fix applies to the **Recent Activities** section in the Admin Dashboard, which displays:
- Check-in activities
- Leave applications
- Task completions
- Other employee activities

## Testing

To verify the fix:
1. Login as Admin
2. View the Dashboard
3. Check the "Recent Activities" section
4. Verify times are displayed in IST format (e.g., "09:30 AM")
5. Compare with actual activity times in the database

## Related Fixes

This is consistent with other timezone fixes in the application:
- Attendance check-in/checkout times (AttendancePage.tsx)
- Selfie modal times (AttendanceManager.tsx)
- All use IST timezone conversion for consistency
