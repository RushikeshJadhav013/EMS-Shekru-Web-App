# Logout Pause/Resume Fix Summary

## Problem
When a user logs out (not checkout), the app should treat that logout as a pause: record the logout timestamp to start Offline time and pause Online time. When the same user logs back in (and they were already checked-in), treat the login as a resume: record the resume timestamp, add the offline duration (login − logout) to Offline time, and continue adding to Online time from its previous accumulated value.

Previously, logging out then logging back in showed the same incorrect value (e.g. "5 hrs – 36 mins") in both Online and Offline fields.

## Solution Overview
Implemented proper timestamp-based pause/resume logic that:
1. **Logout = Pause**: Records logout timestamp and sets user offline
2. **Login = Resume**: Records login timestamp, calculates offline duration, and resumes online tracking
3. **Persistent State**: Maintains pause/resume timestamps across sessions
4. **Accurate Calculations**: Online time only increases when actually online, Offline time only increases during actual logged-out periods

## Changes Made

### 1. Backend Changes (`Backend/app/routes/attendance_routes.py`)

#### Updated Logout Endpoint
- Changed from simple logout to pause-aware logout
- Records logout timestamp as offline status entry
- Preserves attendance session (doesn't checkout)

#### Added Login Resume Endpoint
- New `/attendance/login-resume` endpoint
- Calculates offline duration from logout to login
- Records login timestamp as online status entry
- Resumes online time tracking from previous accumulated value

#### Enhanced Working Hours Calculation
- Updated `calculate_working_hours()` to properly handle pause/resume periods
- Tracks both online and offline time separately
- Returns `total_offline_seconds` in addition to `total_seconds`
- Chronologically processes status logs for accurate time calculation

### 2. Frontend Changes

#### AuthContext (`Frontend/src/contexts/AuthContext.tsx`)
- **Logout Function**: Now calls `/attendance/logout` endpoint with timestamp before clearing session
- **Login Function**: Calls `/attendance/login-resume` endpoint after successful authentication

#### AttendanceWithToggle (`Frontend/src/pages/attendance/AttendanceWithToggle.tsx`)
- **Backend Sync**: Updated to use `total_offline_seconds` from backend response
- **Status Preservation**: Properly initializes timer state when resuming from logout
- **Timer Logic**: Enhanced to handle pause/resume scenarios correctly

## Key Features

### ✅ Proper Pause/Resume Logic
- Logout records exact timestamp and pauses online timer
- Login calculates offline duration and resumes online timer
- No time is lost or double-counted

### ✅ Persistent State
- Online/offline status persists across browser sessions
- Timer state is restored when user logs back in
- Backend maintains complete audit trail of status changes

### ✅ Accurate Time Tracking
- Online time: Only counts when user is actually online and logged in
- Offline time: Only counts actual logout periods, not manual pause/resume
- No overlap or gaps in time tracking

### ✅ Backward Compatibility
- Existing pause/resume functionality (manual toggle) unchanged
- Checkout behavior unchanged
- All existing attendance features preserved

## Testing

Created `Backend/test_logout_pause_resume.py` to verify:
1. User can login and check-in
2. Online time accumulates while logged in
3. Logout properly pauses and records offline status
4. Offline time accumulates while logged out
5. Login resumes and restores online status
6. Working hours calculation reflects accurate online/offline split

## Usage Example

```
1. User checks in at 9:00 AM → Online timer starts
2. User works until 11:00 AM → 2 hours online time
3. User logs out at 11:00 AM → Online timer pauses, offline timer starts
4. User logs back in at 11:30 AM → Offline timer stops (30 min), online timer resumes
5. User continues working until 5:00 PM → Additional 5.5 hours online time
6. Final result: 7.5 hours online, 0.5 hours offline
```

## Files Modified
- `Backend/app/routes/attendance_routes.py` - Added pause/resume endpoints and logic
- `Frontend/src/contexts/AuthContext.tsx` - Updated login/logout to call pause/resume endpoints  
- `Frontend/src/pages/attendance/AttendanceWithToggle.tsx` - Enhanced timer sync and state management
- `Backend/test_logout_pause_resume.py` - Test script to verify functionality

The fix ensures that logout/login cycles are properly tracked as pause/resume periods, providing accurate time tracking that distinguishes between actual work time (online) and break time (offline due to logout).