# Selfie Modal Time Display Fix

## Issue
In the Admin/HR attendance viewing page, when viewing employee selfies (check-in and check-out photos), the displayed times were incorrect. The times shown on the selfie overlay were not matching the actual check-in/checkout times and were not properly converted to IST (Indian Standard Time).

## Root Cause
The selfie modal was using `format(new Date(selectedRecord.checkInTime), 'hh:mm a')` which:
- Doesn't handle timezone conversion properly
- Shows raw UTC time instead of IST
- Doesn't account for ISO datetime strings with timezone info

## Solution
Updated the selfie modal to use the existing `formatIST()` function which:
- Properly handles ISO datetime strings
- Converts UTC time to IST (Asia/Kolkata timezone)
- Handles both datetime strings and time-only strings
- Provides consistent time formatting across the application

## Changes Made

### File: `Frontend/src/pages/attendance/AttendanceManager.tsx`

**Before:**
```tsx
<p className="font-medium">
  Check-in: {selectedRecord?.checkInTime ? format(new Date(selectedRecord.checkInTime), 'hh:mm a') : 'N/A'}
</p>

<p className="font-medium">
  Check-out: {format(new Date(selectedRecord.checkOutTime), 'hh:mm a')}
</p>
```

**After:**
```tsx
<p className="font-medium">
  Check-in: {selectedRecord?.checkInTime ? formatIST(selectedRecord.date, selectedRecord.checkInTime) : 'N/A'}
</p>

<p className="font-medium">
  Check-out: {formatIST(selectedRecord.date, selectedRecord.checkOutTime)}
</p>
```

## How formatIST Works

```typescript
const formatIST = (dateString: string, timeString?: string) => {
  if (!timeString) return '-';
  
  let date: Date;
  if (timeString.includes('T')) {
    // ISO datetime string
    if (timeString.includes('Z') || timeString.includes('+') || timeString.includes('-', 10)) {
      date = new Date(timeString); // Has timezone info
    } else {
      date = new Date(timeString + 'Z'); // Assume UTC
    }
  } else {
    // Time-only string (HH:MM:SS)
    date = new Date(`${dateString}T${timeString}Z`); // Combine with date, assume UTC
  }
  
  // Convert to IST and format
  return date.toLocaleString('en-IN', { 
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  });
};
```

## Benefits
- ✅ Accurate time display in IST timezone
- ✅ Consistent with other time displays in the application
- ✅ Properly handles different datetime formats from backend
- ✅ Shows correct check-in and check-out times on selfie overlays
- ✅ No more timezone confusion for admins/HR managers

## Testing
To verify the fix:
1. Login as Admin or HR Manager
2. Navigate to Attendance Management
3. Click on any employee's selfie to view details
4. Check that the times shown on check-in and check-out selfies match the times in the attendance table
5. Verify times are displayed in IST (Indian Standard Time)
