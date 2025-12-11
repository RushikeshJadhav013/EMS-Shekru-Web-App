# Timezone Quick Reference Guide

## Import Statement
```typescript
import { 
  formatIST, 
  formatDateTimeIST, 
  formatTimeIST, 
  formatDateIST, 
  todayIST, 
  nowIST,
  parseToIST,
  formatDistanceToNowIST,
  formatDateTimeComponentsIST 
} from '@/utils/timezone';
```

## Common Use Cases

### 1. Display Current Date
```typescript
// Get today's date as string (yyyy-MM-dd)
const today = todayIST(); // "2025-12-04"

// Get current Date object in IST
const now = nowIST(); // Date object in IST timezone
```

### 2. Format Backend Timestamps
```typescript
// Backend sends: "2025-12-04T08:30:00Z" (UTC)
// Display as: "Dec 04, 2025 14:00" (IST)
const displayTime = formatDateTimeIST(backendTimestamp);

// Custom format
const customFormat = formatDateTimeIST(backendTimestamp, 'dd/MM/yyyy HH:mm');
```

### 3. Format Dates Only
```typescript
// Display date without time
const dateOnly = formatDateIST(backendDate); // "2025-12-04"
const readableDate = formatDateIST(backendDate, 'dd MMM yyyy'); // "04 Dec 2025"
```

### 4. Format Times Only
```typescript
// Display time without date
const timeOnly = formatTimeIST(backendTimestamp); // "14:30:00"
const time12h = formatTimeIST(backendTimestamp, 'hh:mm a'); // "02:30 PM"
```

### 5. Relative Time (e.g., "2 hours ago")
```typescript
// For notifications, activity feeds
const relativeTime = formatDistanceToNowIST(timestamp); // "2 hours ago"
```

### 6. Attendance Time Display
```typescript
// When date and time come separately from backend
const displayTime = formatDateTimeComponentsIST(
  '2025-12-04',           // date string
  '08:30:00',             // time string (UTC)
  'hh:mm a'               // format
); // "02:00 PM" (IST)
```

### 7. Parse Backend Dates
```typescript
// Parse and validate backend date
const istDate = parseToIST(backendDateString);
if (istDate) {
  // Date is valid, use it
  console.log(istDate);
} else {
  // Date is invalid
  console.log('Invalid date');
}
```

## Format String Reference

### Date Formats
- `'yyyy-MM-dd'` → 2025-12-04
- `'dd/MM/yyyy'` → 04/12/2025
- `'MMM dd, yyyy'` → Dec 04, 2025
- `'dd MMM yyyy'` → 04 Dec 2025
- `'MMMM dd, yyyy'` → December 04, 2025
- `'PPP'` → December 4th, 2025 (long format)

### Time Formats
- `'HH:mm:ss'` → 14:30:00 (24-hour)
- `'HH:mm'` → 14:30 (24-hour)
- `'hh:mm a'` → 02:30 PM (12-hour)
- `'hh:mm:ss a'` → 02:30:00 PM (12-hour)

### Date-Time Formats
- `'MMM dd, yyyy HH:mm'` → Dec 04, 2025 14:30
- `'dd/MM/yyyy HH:mm'` → 04/12/2025 14:30
- `'yyyy-MM-dd HH:mm:ss'` → 2025-12-04 14:30:00

## Migration Examples

### Before (UTC)
```typescript
// ❌ Old way - displays UTC time
const time = new Date(timestamp).toLocaleString();
const date = format(new Date(), 'yyyy-MM-dd');
```

### After (IST)
```typescript
// ✅ New way - displays IST time
const time = formatDateTimeIST(timestamp);
const date = todayIST();
```

## Component Examples

### Attendance Component
```typescript
const formatAttendanceTime = (dateString: string, timeString?: string) => {
  if (!timeString) return '-';
  return formatDateTimeComponentsIST(dateString, timeString, 'hh:mm a');
};

// Usage
<span>{formatAttendanceTime(record.date, record.checkInTime)}</span>
```

### Task Component
```typescript
const formatDeadline = (deadline: string | null) => {
  if (!deadline) return 'No deadline';
  const date = parseToIST(deadline);
  return date ? formatDateIST(date, 'MMM dd, yyyy') : 'Invalid date';
};
```

### Notification Component
```typescript
<span className="text-xs text-muted-foreground">
  {formatDistanceToNowIST(notification.createdAt)}
</span>
```

## Important Notes

1. **Backend Integration**: Backend stores UTC, frontend displays IST
2. **No Backend Changes**: All timezone conversion happens in frontend
3. **Consistent Usage**: Always use the timezone utility functions
4. **Date Pickers**: Automatically use IST for current date
5. **Exports**: Report exports use IST dates in filenames

## Timezone Info
- **Timezone**: Asia/Kolkata
- **Abbreviation**: IST (Indian Standard Time)
- **UTC Offset**: +05:30
- **No DST**: India does not observe daylight saving time
