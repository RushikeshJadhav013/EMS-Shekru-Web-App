# Timezone Deployment Checklist

## ✅ Pre-Deployment Verification

### 1. Installation
- [x] `date-fns-tz@^3.2.0` added to package.json
- [x] Dependencies installed (`npm install`)
- [x] No installation errors

### 2. Build Verification
- [x] Build completes successfully (`npm run build`)
- [x] No TypeScript errors
- [x] No compilation errors
- [x] Dist folder generated

### 3. Code Quality
- [x] All timezone utility functions created
- [x] All attendance pages updated
- [x] All task management updated
- [x] All notification components updated
- [x] All dashboard components updated
- [x] UI components (date-picker, calendar) updated

### 4. Documentation
- [x] TIMEZONE_UPDATE.md created
- [x] TIMEZONE_QUICK_REFERENCE.md created
- [x] TIMEZONE_IMPLEMENTATION_SUMMARY.md created
- [x] TIMEZONE_DEPLOYMENT_CHECKLIST.md created
- [x] timezone-test.ts utility created

## 📋 Post-Deployment Testing

### Critical Features to Test

#### 1. Attendance System
- [ ] Check-in time displays in IST
- [ ] Check-out time displays in IST
- [ ] Attendance history shows IST times
- [ ] Manager view shows all times in IST
- [ ] Export attendance reports use IST dates

**Test Case:**
1. Check in at 9:00 AM IST
2. Verify displayed time is 9:00 AM (not 3:30 AM UTC)
3. Check attendance history
4. Export report and verify dates

#### 2. Task Management
- [ ] Task creation timestamp in IST
- [ ] Task deadline displays in IST
- [ ] Task completion time in IST
- [ ] Task comments show IST timestamps
- [ ] Task export uses IST dates

**Test Case:**
1. Create a task with deadline
2. Verify deadline shows IST date
3. Complete task and check completion time
4. Export tasks and verify dates

#### 3. Notifications
- [ ] Notification timestamps show relative time in IST
- [ ] "X hours ago" calculated from IST
- [ ] Notification list sorted by IST time

**Test Case:**
1. Trigger a notification
2. Verify it shows "Just now" or "X minutes ago"
3. Wait and verify relative time updates correctly

#### 4. Leave Management
- [ ] Leave request dates in IST
- [ ] Leave approval timestamps in IST
- [ ] Leave calendar shows IST dates

**Test Case:**
1. Submit leave request for tomorrow
2. Verify date is correct in IST
3. Approve/reject and check timestamp

#### 5. Reports & Analytics
- [ ] Report date filters use IST
- [ ] Monthly reports show IST month
- [ ] Export filenames include IST dates
- [ ] Report data shows IST timestamps

**Test Case:**
1. Generate monthly report
2. Verify month is current IST month
3. Export and check filename date
4. Verify all timestamps in report

#### 6. Dashboards
- [ ] Admin dashboard shows IST times
- [ ] Manager dashboard shows IST times
- [ ] Employee dashboard shows IST times
- [ ] Activity logs display IST timestamps

**Test Case:**
1. Open each dashboard
2. Verify all times are in IST
3. Check activity logs

## 🔧 Debugging Tools

### Browser Console Tests
Open browser console and run:

```javascript
// Load test utilities
import('/src/utils/timezone-test.js').then(m => {
  // Run all tests
  m.runTimezoneTests();
  
  // Verify timezone
  m.verifyTimezone();
  
  // Test specific timestamp
  m.compareUTCandIST('2025-12-04T08:30:00Z');
  
  // Test attendance formatting
  m.testAttendanceFormatting();
});
```

Or use the global object:
```javascript
timezoneTests.runTimezoneTests();
timezoneTests.verifyTimezone();
```

### Manual Verification
1. **Check Current Time:**
   - Open any page with timestamps
   - Compare with your system clock
   - Should match IST (UTC+5:30)

2. **Check Timezone Offset:**
   - Open browser console
   - Run: `new Date().getTimezoneOffset()`
   - Should return `-330` (for IST, -5.5 hours in minutes)

3. **Verify Backend Integration:**
   - Check network tab in DevTools
   - Verify API requests still send UTC
   - Verify API responses are in UTC
   - Verify frontend converts to IST for display

## 🚨 Common Issues & Solutions

### Issue 1: Times Still Showing UTC
**Symptoms:** Times appear 5.5 hours behind
**Solution:** 
- Clear browser cache
- Hard refresh (Ctrl+Shift+R)
- Verify `date-fns-tz` is installed
- Check console for errors

### Issue 2: Build Fails
**Symptoms:** Build errors mentioning timezone functions
**Solution:**
- Run `npm install` again
- Verify `date-fns-tz` in package.json
- Check for syntax errors in timezone.ts

### Issue 3: Incorrect Time Display
**Symptoms:** Times are off by hours
**Solution:**
- Verify APP_TIMEZONE is 'Asia/Kolkata'
- Check browser timezone settings
- Run `timezoneTests.verifyTimezone()` in console

### Issue 4: Date Picker Issues
**Symptoms:** Date picker shows wrong dates
**Solution:**
- Verify date-picker.tsx imports timezone utils
- Check if `nowIST()` is used for defaults
- Clear browser cache

## 📊 Monitoring

### Metrics to Watch
1. **User Reports:** Any complaints about incorrect times
2. **Error Logs:** Check for timezone-related errors
3. **API Calls:** Verify UTC is still being sent to backend
4. **Data Integrity:** Ensure no data corruption

### Log Checks
Look for these in browser console:
- ✅ No "Invalid Date" errors
- ✅ No timezone conversion errors
- ✅ No "undefined" in time displays

## 🎯 Success Criteria

### Must Have
- [x] All times display in IST (UTC+5:30)
- [x] No TypeScript errors
- [x] Build succeeds
- [x] No console errors
- [ ] User testing confirms correct times

### Nice to Have
- [x] Comprehensive documentation
- [x] Testing utilities available
- [x] Quick reference guide
- [ ] User training completed

## 📞 Rollback Plan

If critical issues are found:

1. **Immediate Rollback:**
   ```bash
   git revert <commit-hash>
   npm install
   npm run build
   ```

2. **Partial Rollback:**
   - Keep timezone utility
   - Revert specific component changes
   - Test incrementally

3. **Investigation:**
   - Check browser console
   - Review error logs
   - Run timezone tests
   - Compare with documentation

## 📝 Sign-Off

### Development Team
- [ ] Code reviewed
- [ ] Tests passed
- [ ] Documentation complete
- [ ] Build verified

### QA Team
- [ ] Attendance tested
- [ ] Tasks tested
- [ ] Notifications tested
- [ ] Reports tested
- [ ] Dashboards tested

### Deployment Team
- [ ] Backup created
- [ ] Deployment plan reviewed
- [ ] Rollback plan ready
- [ ] Monitoring configured

---

**Deployment Date:** _____________
**Deployed By:** _____________
**Verified By:** _____________
**Status:** ⏳ Pending / ✅ Complete / ❌ Issues Found
