# Timezone Update - Asia/Kolkata (IST)

## Overview
The entire frontend has been updated to use the **Asia/Kolkata (IST - Indian Standard Time)** timezone globally. All displayed times now show in IST instead of UTC.

## Changes Made

### 1. New Timezone Utility (`src/utils/timezone.ts`)
Created a centralized timezone utility that provides:
- `toIST()` - Convert any date to IST timezone
- `formatIST()` - Format dates in IST with custom format strings
- `formatDateTimeIST()` - Format date-time in IST (default: 'MMM dd, yyyy HH:mm')
- `formatTimeIST()` - Format time only in IST (default: 'HH:mm:ss')
- `formatDateIST()` - Format date only in IST (default: 'yyyy-MM-dd')
- `formatDistanceToNowIST()` - Relative time in IST (e.g., "2 hours ago")
- `nowIST()` - Get current date-time in IST
- `todayIST()` - Get current date string in IST
- `parseToIST()` - Parse backend date strings to IST
- `formatBackendDateIST()` - Format backend dates to IST display format
- `formatDateTimeComponentsIST()` - Format separate date and time components

### 2. Package Added
- **date-fns-tz** (v3.2.0) - For timezone conversion support

### 3. Files Updated

#### Attendance Pages
- `src/pages/attendance/AttendanceWithToggle.tsx`
- `src/pages/attendance/AttendanceManager.tsx`
- `src/pages/attendance/AttendancePage.tsx`
- `src/components/attendance/AttendanceWithLocation.tsx`

**Changes:**
- All check-in/check-out times now display in IST
- Date filtering uses IST dates
- Attendance history shows IST timestamps
- Replaced local `formatIST` functions with centralized utility

#### Task Management
- `src/pages/tasks/TaskManagement.tsx`

**Changes:**
- Task creation timestamps in IST
- Deadline displays in IST
- Task completion times in IST
- Export reports use IST dates

#### Notifications
- `src/components/notifications/NotificationBell.tsx`

**Changes:**
- Notification timestamps display relative time in IST
- Simplified date parsing logic

#### Leave Management
- `src/pages/leaves/LeaveManagement.tsx`

**Changes:**
- Leave request dates in IST
- Leave approval timestamps in IST

#### Reports & Exports
- `src/components/reports/ExportDialog.tsx`
- `src/pages/reports/Reports.tsx`

**Changes:**
- Report date ranges use IST
- Export filenames include IST dates
- Monthly/yearly filters use IST

#### Dashboards
- `src/pages/admin/AdminDashboard.tsx`

**Changes:**
- Activity timestamps in IST
- Dashboard statistics use IST dates

#### Other Components
- `src/components/rating/RatingDialog.tsx` - Rating timestamps in IST
- `src/pages/inbox/Inbox.tsx` - Message timestamps in IST
- `src/pages/shifts/TeamShifts.tsx` - Shift schedules in IST
- `src/pages/shifts/ShiftScheduleManagement.tsx` - Shift assignments in IST
- `src/pages/access/AccessControl.tsx` - Access logs in IST

#### UI Components
- `src/components/ui/date-picker.tsx` - Default to IST for current date
- `src/components/ui/calendar-with-select.tsx` - Calendar displays IST dates

## How It Works

### Backend Integration
The backend stores all timestamps in UTC (as it should). The frontend:
1. **Receives** UTC timestamps from the backend
2. **Converts** them to IST for display using the timezone utility
3. **Sends** UTC timestamps back to the backend when creating/updating records

### Example Usage

```typescript
import { formatDateTimeIST, todayIST, nowIST, parseToIST } from '@/utils/timezone';

// Display a backend timestamp
const displayTime = formatDateTimeIST(backendTimestamp); // "Dec 04, 2025 14:30"

// Get today's date in IST
const today = todayIST(); // "2025-12-04"

// Get current time in IST
const now = nowIST(); // Date object in IST

// Parse and display backend date
const istDate = parseToIST(backendDateString);
```

### Attendance Time Display
Attendance times are formatted using a helper function:
```typescript
const formatAttendanceTime = (dateString: string, timeString?: string) => {
  if (!timeString) return '-';
  return formatDateTimeComponentsIST(dateString, timeString, 'hh:mm a');
};
```

This handles both:
- Full ISO datetime strings from the backend
- Separate date and time components

## Installation

To install the required package:
```bash
cd Frontend
npm install
```

This will install `date-fns-tz@^3.2.0` which is required for timezone conversion.

## Testing

After installation, verify that:
1. All attendance times show in IST (UTC+5:30)
2. Task deadlines and timestamps are in IST
3. Notification times are relative to IST
4. Leave dates are in IST
5. Report exports use IST dates
6. Dashboard statistics use IST

## Notes

- The timezone is set to `Asia/Kolkata` which is the same as IST (UTC+5:30)
- All date displays throughout the application now use IST
- The backend continues to store UTC timestamps (no backend changes needed)
- Date pickers and calendars default to IST dates
- Relative time displays (e.g., "2 hours ago") are calculated from IST

## Timezone Constant

The application timezone is defined as a constant:
```typescript
export const APP_TIMEZONE = 'Asia/Kolkata';
```

If you need to change the timezone in the future, update this constant in `src/utils/timezone.ts`.
