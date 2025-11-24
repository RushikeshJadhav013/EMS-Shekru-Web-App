# Calendar with Year/Month Dropdowns - Implementation Guide

## Overview
A new enhanced calendar component has been created that includes year and month dropdown selectors, making it easy to navigate to any month/year quickly.

## Component Location
`Frontend/src/components/ui/calendar-with-select.tsx`

## Features
- ✅ Month dropdown (January - December)
- ✅ Year dropdown (10 years before and after current year)
- ✅ Previous/Next month navigation buttons
- ✅ Beautiful gradient styling matching the app theme
- ✅ Fully responsive
- ✅ Supports all Calendar props from react-day-picker

## Usage

### 1. Import the Component
```typescript
import { CalendarWithSelect } from '@/components/ui/calendar-with-select';
```

### 2. Basic Usage
```typescript
const [selectedDate, setSelectedDate] = useState<Date | undefined>(new Date());

<CalendarWithSelect
  mode="single"
  selected={selectedDate}
  onSelect={setSelectedDate}
  currentMonth={selectedDate}
  onMonthChange={setSelectedDate}
  className="rounded-xl border-2 shadow-lg p-4"
/>
```

### 3. With Modifiers (Holidays, etc.)
```typescript
<CalendarWithSelect
  mode="single"
  selected={selectedDate}
  onSelect={setSelectedDate}
  currentMonth={selectedDate}
  onMonthChange={setSelectedDate}
  modifiers={{
    holiday: holidays.map(h => h.date),
    weekend: (date) => date.getDay() === 0 || date.getDay() === 6,
  }}
  modifiersClassNames={{
    holiday: 'bg-red-500 text-white',
    weekend: 'bg-blue-100',
  }}
/>
```

## Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `currentMonth` | `Date` | No | The currently displayed month (default: new Date()) |
| `onMonthChange` | `(date: Date) => void` | No | Callback when month/year changes |
| All other props | - | No | Supports all react-day-picker props (mode, selected, onSelect, modifiers, etc.) |

## Pages Already Updated
- ✅ Leave Management (`Frontend/src/pages/leaves/LeaveManagement.tsx`)

## Pages That Can Use This Component

### Attendance Pages
- `Frontend/src/pages/attendance/AttendancePage.tsx`
- `Frontend/src/pages/attendance/AttendanceManager.tsx`

### Reports
- `Frontend/src/pages/reports/Reports.tsx` (if it has calendars)

### Dashboard Pages
- `Frontend/src/pages/admin/AdminDashboard.tsx`
- Any other dashboard with calendar views

## How to Update Other Pages

### Step 1: Import
Replace:
```typescript
import { Calendar } from '@/components/ui/calendar';
```

With:
```typescript
import { CalendarWithSelect } from '@/components/ui/calendar-with-select';
```

### Step 2: Update Component
Replace:
```typescript
<Calendar
  mode="single"
  selected={date}
  onSelect={setDate}
  // ... other props
/>
```

With:
```typescript
<CalendarWithSelect
  mode="single"
  selected={date}
  onSelect={setDate}
  currentMonth={date}
  onMonthChange={setDate}
  // ... other props
/>
```

## Styling
The component uses the same gradient and styling theme as the rest of the application:
- Blue/Indigo gradients for selectors
- Smooth transitions and hover effects
- Shadow effects for depth
- Dark mode support

## Example: Full Implementation

```typescript
import React, { useState } from 'react';
import { CalendarWithSelect } from '@/components/ui/calendar-with-select';

export default function MyPage() {
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(new Date());

  return (
    <div className="p-6">
      <CalendarWithSelect
        mode="single"
        selected={selectedDate}
        onSelect={setSelectedDate}
        currentMonth={selectedDate}
        onMonthChange={setSelectedDate}
        className="rounded-xl border-2 shadow-lg p-4 bg-white dark:bg-gray-950"
      />
    </div>
  );
}
```

## Benefits
1. **Better UX**: Users can quickly jump to any month/year
2. **Consistent**: Same look and feel across all pages
3. **Accessible**: Keyboard navigation supported
4. **Responsive**: Works on mobile and desktop
5. **Flexible**: Supports all existing Calendar features

## Notes
- The year dropdown shows 10 years before and 10 years after the current year (21 years total)
- Month names are in English (can be localized if needed)
- The component maintains all the functionality of the original Calendar component
- Navigation buttons (< >) are positioned on the sides for easy access
