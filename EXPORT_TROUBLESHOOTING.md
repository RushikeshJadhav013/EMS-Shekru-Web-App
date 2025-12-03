# Export Feature Troubleshooting Guide

## Issue: 404 Not Found Error

### Symptoms
```
XHR GET https://staffly.space/reports/export?format=csv&start_date=2025-11-02&end_date=2025-12-02
[HTTP/1.1 404 Not Found]
Export error: Error: Export failed
```

### Root Cause
The backend server hasn't been restarted after adding the new export endpoint.

### Solution

#### Option 1: Use the Restart Script (Recommended)
```bash
cd Backend
chmod +x restart_backend.sh
./restart_backend.sh
```

#### Option 2: Manual Restart

**If using systemd:**
```bash
# Find the service name
systemctl list-units --type=service | grep -E "staffly|employee|ems"

# Restart the service
sudo systemctl restart <service-name>

# Check status
sudo systemctl status <service-name>
```

**If using PM2:**
```bash
# List processes
pm2 list

# Restart the process
pm2 restart <process-name>

# Check logs
pm2 logs <process-name>
```

**If using Supervisor:**
```bash
# Check status
sudo supervisorctl status

# Restart
sudo supervisorctl restart <process-name>
```

**If running manually:**
```bash
# Find the process
ps aux | grep uvicorn

# Kill it
kill <PID>

# Start again
cd Backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### Option 3: Development Mode
```bash
cd Backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Verification

#### 1. Check if endpoint exists
```bash
curl http://localhost:8000/docs
```
Look for `/reports/export` in the API documentation.

#### 2. Test the endpoint
```bash
# Get a token first (login to the app, then check localStorage.getItem('token'))
TOKEN="your-token-here"

# Test the endpoint
curl -X GET "http://localhost:8000/reports/export?format=csv&start_date=2024-11-01&end_date=2024-12-01" \
  -H "Authorization: Bearer $TOKEN" \
  -o test_export.csv
```

#### 3. Use the test script
```bash
cd Backend
python3 test_export_endpoint.py
```

## Issue: 401 Unauthorized Error

### Symptoms
```
[HTTP/1.1 401 Unauthorized]
```

### Solutions

1. **Check if logged in:**
   - Open browser console
   - Run: `localStorage.getItem('token')`
   - If null, login again

2. **Token expired:**
   - Logout and login again
   - Token will be refreshed

3. **Check backend authentication:**
   ```bash
   # Check backend logs for authentication errors
   tail -f /var/log/staffly/backend.log
   ```

## Issue: 500 Internal Server Error

### Symptoms
```
[HTTP/1.1 500 Internal Server Error]
```

### Solutions

1. **Check backend logs:**
   ```bash
   # If using systemd
   sudo journalctl -u <service-name> -f
   
   # If using PM2
   pm2 logs <process-name>
   
   # If manual
   # Check the terminal where uvicorn is running
   ```

2. **Common causes:**
   - Missing database tables
   - Database connection issues
   - Missing Python dependencies

3. **Install missing dependencies:**
   ```bash
   cd Backend
   pip install -r requirements.txt
   ```

4. **Check database connection:**
   ```python
   # In Python console
   from app.db.database import engine
   from sqlalchemy import text
   
   with engine.connect() as conn:
       result = conn.execute(text("SELECT 1"))
       print(result.fetchone())
   ```

## Issue: Empty or Corrupted Export File

### Symptoms
- File downloads but is empty
- File downloads but can't be opened
- CSV shows garbled text
- PDF shows errors

### Solutions

1. **Check date range:**
   - Ensure start_date < end_date
   - Ensure dates are in correct format (YYYY-MM-DD)
   - Ensure there's data in the selected range

2. **Check employee data:**
   ```sql
   -- Check if employees exist
   SELECT COUNT(*) FROM users WHERE is_active = 1;
   
   -- Check if attendance data exists
   SELECT COUNT(*) FROM attendance;
   
   -- Check if task data exists
   SELECT COUNT(*) FROM tasks;
   ```

3. **Test with smaller dataset:**
   - Try exporting single employee first
   - Try shorter date range
   - Check if specific employee has data

4. **Check file encoding:**
   - CSV should be UTF-8
   - PDF should be binary

## Issue: Slow Export Performance

### Symptoms
- Export takes very long time
- Browser shows "waiting for response"
- Timeout errors

### Solutions

1. **Reduce date range:**
   - Export smaller time periods
   - Export month by month instead of yearly

2. **Export single employee:**
   - Instead of all employees at once
   - Export department by department

3. **Optimize database:**
   ```sql
   -- Add indexes if missing
   CREATE INDEX idx_attendance_user_date ON attendance(user_id, check_in);
   CREATE INDEX idx_tasks_assigned ON tasks(assigned_to, status);
   CREATE INDEX idx_leaves_user_date ON leaves(user_id, start_date, end_date);
   ```

4. **Increase timeout:**
   ```typescript
   // In ExportDialog.tsx
   const response = await fetch(`${url}`, {
     headers: headers,
     signal: AbortSignal.timeout(60000) // 60 seconds
   });
   ```

## Issue: CORS Errors

### Symptoms
```
Access to fetch at 'https://staffly.space/reports/export' from origin 'https://stafflyhrms.netlify.app' has been blocked by CORS policy
```

### Solutions

1. **Check CORS configuration in backend:**
   ```python
   # In Backend/app/main.py
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # Or specific origins
       allow_credentials=True,
       allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
       allow_headers=["*"],
   )
   ```

2. **Restart backend after CORS changes**

3. **Check nginx configuration:**
   ```nginx
   # In nginx.conf
   add_header 'Access-Control-Allow-Origin' '*';
   add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
   add_header 'Access-Control-Allow-Headers' '*';
   ```

## Testing Checklist

Before reporting an issue, please verify:

- [ ] Backend server is running
- [ ] Backend has been restarted after code changes
- [ ] You are logged in (token exists in localStorage)
- [ ] Token is not expired (try logout/login)
- [ ] Date range is valid (start < end)
- [ ] Date format is correct (YYYY-MM-DD)
- [ ] There is data in the selected date range
- [ ] Browser console shows no JavaScript errors
- [ ] Network tab shows the request is being made
- [ ] Backend logs show no errors

## Debug Mode

### Enable detailed logging in frontend:
```typescript
// In ExportDialog.tsx, add before fetch:
console.log('Export params:', {
  format: exportFormat,
  start_date: format(startDate, 'yyyy-MM-dd'),
  end_date: format(endDate, 'yyyy-MM-dd'),
  employee_id: selectedEmployee?.id
});
```

### Enable detailed logging in backend:
```python
# In report_routes.py, add at start of export function:
print(f"Export request: format={format}, start={start_date}, end={end_date}, employee={employee_id}")
```

## Getting Help

If issues persist:

1. **Collect information:**
   - Browser console errors (full stack trace)
   - Network tab (request/response details)
   - Backend logs (last 50 lines)
   - Python version: `python3 --version`
   - FastAPI version: `pip show fastapi`

2. **Check documentation:**
   - `EXPORT_FEATURE_IMPLEMENTATION.md` - Feature details
   - `Backend/app/routes/report_routes.py` - Endpoint code
   - `Frontend/src/components/reports/ExportDialog.tsx` - Frontend code

3. **Test with curl:**
   ```bash
   # This bypasses frontend issues
   curl -X GET "http://localhost:8000/reports/export?format=csv&start_date=2024-11-01&end_date=2024-12-01" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -v
   ```

4. **Check API docs:**
   - Open: http://localhost:8000/docs
   - Find `/reports/export` endpoint
   - Try "Try it out" button
   - Check if it works from Swagger UI

## Quick Fixes Summary

| Issue | Quick Fix |
|-------|-----------|
| 404 Not Found | Restart backend server |
| 401 Unauthorized | Logout and login again |
| 500 Server Error | Check backend logs |
| Empty file | Check date range and data |
| Slow export | Reduce date range |
| CORS error | Check CORS config and restart |
| Timeout | Increase timeout or reduce data |

## Production Deployment

After fixing issues in development:

1. **Update production backend:**
   ```bash
   git pull origin main
   cd Backend
   pip install -r requirements.txt
   sudo systemctl restart staffly
   ```

2. **Update production frontend:**
   ```bash
   git pull origin main
   cd Frontend
   npm install
   npm run build
   # Deploy build folder to hosting
   ```

3. **Verify in production:**
   - Test export with small dataset first
   - Monitor backend logs
   - Check performance
   - Test with different browsers

## Contact

For additional support:
- Check backend logs: `/var/log/staffly/`
- Check application logs in browser console
- Review the implementation documentation
