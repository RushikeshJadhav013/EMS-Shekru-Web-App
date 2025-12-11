# Deployment Fixes for Common Issues

## Issue 1: 413 Payload Too Large Error

### Problem
When uploading attendance with selfies, you get:
```
Cross-Origin Request Blocked: The Same Origin Policy disallows reading the remote resource at https://staffly.space/attendance/check-out/json. (Reason: CORS header 'Access-Control-Allow-Origin' missing). Status code: 413.
```

### Root Cause
The base64-encoded selfie images are too large for the default web server configuration.

### Solutions Implemented

#### Frontend Fix (Already Applied)
- ✅ Images are now automatically compressed before upload
- Compression settings: max width 800px, quality 70%
- This reduces payload size by 60-80%

#### Backend/Server Fix (Requires Server Configuration)

**For Nginx:**
```bash
# Edit your nginx configuration
sudo nano /etc/nginx/sites-available/staffly.space

# Add this inside the server block:
client_max_body_size 50M;
client_body_buffer_size 10M;

# Reload nginx
sudo nginx -t
sudo systemctl reload nginx
```

**For Apache:**
```bash
# Edit your apache configuration or .htaccess
LimitRequestBody 52428800

# Restart apache
sudo systemctl restart apache2
```

**For Gunicorn (if using):**
```bash
# Add these flags when starting gunicorn
gunicorn app.main:app \
  --limit-request-line 8190 \
  --limit-request-field_size 8190 \
  --timeout 60
```

**Using the provided nginx.conf:**
```bash
# Copy the provided configuration
sudo cp Backend/nginx.conf /etc/nginx/sites-available/staffly.space

# Update paths in the config file
sudo nano /etc/nginx/sites-available/staffly.space

# Enable the site
sudo ln -s /etc/nginx/sites-available/staffly.space /etc/nginx/sites-enabled/

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

## Issue 2: Invalid or Expired Token Errors

### Problem
Multiple API requests fail with:
```
API request failed: Error: Invalid or expired token
XHR GET https://staffly.space/tasks/notifications [HTTP/1.1 401 Unauthorized]
XHR GET https://staffly.space/leave/notifications [HTTP/1.1 401 Unauthorized]
XHR GET https://staffly.space/shift/notifications [HTTP/1.1 401 Unauthorized]
```

### Root Cause
JWT tokens expire after a certain time, but there's no automatic refresh mechanism.

### Solutions Implemented

#### Automatic Logout on Token Expiration (Already Applied)
- ✅ When a 401 error with "Invalid or expired token" is detected, the user is automatically logged out
- ✅ Auth data is cleared from localStorage
- ✅ User is redirected to login page
- ✅ Notification polling validates token before making requests
- ✅ Notification polling stops and clears auth on 401 errors
- ✅ Network errors are handled silently to reduce console noise

#### Recommendations

1. **Increase Token Expiration Time** (if needed):
   ```python
   # In Backend/app/core/config.py
   JWT_EXPIRATION_HOURS: int = 24  # Add this line
   
   # In Backend/app/routes/auth_routes.py
   # Update token creation to use expiration time
   from datetime import datetime, timedelta
   
   expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
   token_data = {"sub": user.email, "exp": expire}
   ```

2. **Implement Token Refresh** (future enhancement):
   - Add a refresh token endpoint
   - Store refresh tokens securely
   - Automatically refresh access tokens before they expire

3. **Add Token Validation on App Load**:
   - Check if token is still valid when app loads
   - Logout user if token is expired

## Issue 3: CORS Headers Missing on Error Responses

### Problem
CORS headers are missing when the server returns error responses (like 413).

### Solution
Already implemented in `Backend/app/main.py`:
- ✅ All exception handlers now include CORS headers
- ✅ 413, 401, 403, 422, and 500 errors all return proper CORS headers

## Testing the Fixes

### Test Image Compression
1. Open attendance page
2. Try to check in/out with selfie
3. Check browser network tab - payload should be < 5MB

### Test Token Handling
1. Login to the application
2. Wait for token to expire (or manually delete token from localStorage)
3. Try to access any protected page
4. Should automatically redirect to login

### Test Server Configuration
```bash
# Test with a large payload
curl -X POST https://staffly.space/attendance/check-out/json \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d @large_payload.json

# Should return 200 OK, not 413
```

## Monitoring

### Check Nginx Logs
```bash
# Error log
sudo tail -f /var/log/nginx/error.log

# Access log
sudo tail -f /var/log/nginx/access.log
```

### Check Application Logs
```bash
# If using systemd
sudo journalctl -u staffly -f

# If using PM2
pm2 logs staffly
```

## Quick Reference

| Issue | Status | Action Required |
|-------|--------|-----------------|
| Image compression | ✅ Fixed | None - already deployed |
| Token auto-logout | ✅ Fixed | None - already deployed |
| CORS on errors | ✅ Fixed | None - already deployed |
| Server body size | ⚠️ Pending | Configure nginx/apache |

## Support

If issues persist after applying these fixes:
1. Check server logs for specific errors
2. Verify nginx/apache configuration is loaded
3. Test with smaller images first
4. Check browser console for detailed error messages
