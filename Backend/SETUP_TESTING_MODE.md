# Setup Guide: Switch from Production SMTP to Testing Mode with Fixed OTP

## Overview
This guide explains how to:
1. **Stop using Gmail SMTP** in production
2. **Switch to testing mode** with fixed OTP (123456)
3. **Fix the verify-otp endpoint** (already fixed in code)

## What Was Fixed

### 1. Bug Fix in `verify_otp` Function
**Problem**: The `verify-otp` endpoint was checking for OTP records before allowing the testing OTP, causing it to fail even when using the fixed OTP.

**Solution**: Modified `app/core/otp_utils.py` to check for testing OTP FIRST, before checking for records. Now the fixed OTP (123456) will work even if `send-otp` wasn't called.

### 2. Config Class Fix
Fixed indentation issue in `app/core/config.py` where the Config class was incorrectly placed.

## Step-by-Step Setup Instructions

### Step 1: Navigate to Backend Directory
```bash
cd /home/ubuntu/Documents/NewStaffly/EMS-Shekru-Web-App/Backend
```

### Step 2: Set Environment Variables

You have **three options** to set environment variables:

#### Option A: Export in Current Shell Session (Temporary)
```bash
export ENVIRONMENT=testing
export TESTING_OTP=123456
export ENABLE_EMAIL_OTP=false
```

#### Option B: Add to `.env.production` File (Recommended for Production Server)
```bash
# Edit the .env.production file
nano .env.production
# or
vim .env.production
```

Add or update these lines:
```bash
ENVIRONMENT=testing
TESTING_OTP=123456
ENABLE_EMAIL_OTP=false
```

**Note**: The config reads from `.env.production` by default (as configured in `config.py`).

#### Option C: Create `.env.testing` File
```bash
cat > .env.testing << EOF
ENVIRONMENT=testing
TESTING_OTP=123456
ENABLE_EMAIL_OTP=false
DATABASE_URL=mysql+pymysql://staffly:staff9612@localhost/empl
JWT_SECRET=supersecretjwtkey
JWT_ALGORITHM=HS256
OTP_EXPIRY_SECONDS=120
EOF
```

Then update `config.py` to use `.env.testing`:
```python
class Config:
    env_file = ".env.testing"
```

### Step 3: Verify Environment Variables
```bash
# Check if variables are set
echo "ENVIRONMENT: $ENVIRONMENT"
echo "TESTING_OTP: $TESTING_OTP"
echo "ENABLE_EMAIL_OTP: $ENABLE_EMAIL_OTP"
```

### Step 4: Restart the Backend Server

Choose the method based on how your server is running:

#### Method 1: If Using systemd Service
```bash
# Find the service name
sudo systemctl list-units --type=service | grep -E "staffly|employee|ems|backend"

# Restart the service (replace SERVICE_NAME with actual name)
sudo systemctl restart SERVICE_NAME

# Check status
sudo systemctl status SERVICE_NAME

# View logs
sudo journalctl -u SERVICE_NAME -f
```

#### Method 2: If Using PM2
```bash
# List processes
pm2 list

# Restart the backend process (replace PROCESS_NAME with actual name)
pm2 restart PROCESS_NAME

# View logs
pm2 logs PROCESS_NAME
```

#### Method 3: If Using Supervisor
```bash
# List processes
sudo supervisorctl status

# Restart the backend process (replace PROCESS_NAME with actual name)
sudo supervisorctl restart PROCESS_NAME

# View logs
sudo supervisorctl tail -f PROCESS_NAME
```

#### Method 4: Manual Start (If Not Using Process Manager)
```bash
# Stop any running instance
pkill -f "uvicorn app.main:app"

# Start the server
cd /home/ubuntu/Documents/NewStaffly/EMS-Shekru-Web-App/Backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Or for development/testing mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Method 5: Using the Deploy Script
```bash
cd /home/ubuntu/Documents/NewStaffly/EMS-Shekru-Web-App/Backend
./deploy.sh testing
```

### Step 5: Verify the Configuration

#### Test 1: Check Environment Info (Testing Mode Only)
```bash
curl https://staffly.space/auth/debug/environment
```

Expected response:
```json
{
  "environment": "testing",
  "should_use_fixed_otp": true,
  "should_send_email": false,
  "testing_otp": "123456",
  "enable_email_otp": false,
  "active_otps": 0
}
```

#### Test 2: Send OTP (Should Not Send Email)
```bash
curl -X POST "https://staffly.space/auth/send-otp?email=test@example.com"
```

Expected response:
```json
{
  "message": "OTP generated (check console for testing environment)",
  "environment": "testing",
  "otp_method": "console",
  "expires_in_seconds": 120
}
```

**Note**: Check server logs/console - you should see the OTP printed there, NOT sent via email.

#### Test 3: Verify OTP with Fixed Code
```bash
curl -X POST "https://staffly.space/auth/verify-otp?email=test@example.com&otp=123456"
```

Expected response (if user exists and is active):
```json
{
  "access_token": "...",
  "token_type": "bearer",
  "role": "...",
  "user_id": ...,
  "email": "test@example.com",
  "name": "...",
  "environment": "testing"
}
```

### Step 6: Test in Swagger UI

1. Open Swagger docs: `https://staffly.space/docs`
2. Navigate to `/auth/send-otp` endpoint
3. Enter an email and click "Execute"
4. Check the response - should show `"otp_method": "console"`
5. Navigate to `/auth/verify-otp` endpoint
6. Enter the same email and OTP: `123456`
7. Click "Execute" - should return success with access token

## How It Works

### Environment Configuration Logic

1. **ENVIRONMENT=testing**:
   - `should_use_fixed_otp` = `true` (uses fixed OTP: 123456)
   - `should_send_email` = `false` (unless `ENABLE_EMAIL_OTP=true`)

2. **ENABLE_EMAIL_OTP=false**:
   - Prevents email sending even if environment is set to production
   - OTP will be logged to console instead

3. **TESTING_OTP=123456**:
   - Fixed OTP code used for all OTP generation in testing mode
   - Can be verified without calling `send-otp` first (bug fix)

### OTP Flow in Testing Mode

1. **send-otp**:
   - Generates OTP: `123456` (fixed)
   - Stores in memory (OTP_STORE)
   - Logs to console (does NOT send email)
   - Returns success message

2. **verify-otp**:
   - Accepts `123456` even if no record exists (bug fix)
   - Also accepts stored OTP if `send-otp` was called
   - Validates user exists and is active
   - Returns JWT token on success

## Troubleshooting

### Issue: verify-otp Still Not Working

1. **Check environment variables are set**:
   ```bash
   python3 -c "from app.core.config import settings; print(f'ENV: {settings.ENVIRONMENT}, Fixed OTP: {settings.should_use_fixed_otp}, Testing OTP: {settings.TESTING_OTP}')"
   ```

2. **Check server logs** for OTP verification attempts:
   ```bash
   # For systemd
   sudo journalctl -u SERVICE_NAME -f
   
   # For PM2
   pm2 logs PROCESS_NAME
   ```

3. **Verify the fix is applied**:
   ```bash
   grep -A 5 "def verify_otp" app/core/otp_utils.py
   ```
   Should show testing OTP check BEFORE record check.

### Issue: Still Sending Emails

1. **Check ENABLE_EMAIL_OTP**:
   ```bash
   echo $ENABLE_EMAIL_OTP  # Should be empty or "false"
   ```

2. **Check environment**:
   ```bash
   echo $ENVIRONMENT  # Should be "testing" not "production"
   ```

3. **Verify config logic**:
   ```bash
   python3 -c "from app.core.config import settings; print(f'Should send email: {settings.should_send_email}')"
   ```
   Should print `False`.

### Issue: Server Won't Start

1. **Check Python dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Check database connection**:
   ```bash
   mysql -u staffly -p staff9612 -e "SELECT 1" empl
   ```

3. **Check port availability**:
   ```bash
   netstat -tulpn | grep 8000
   ```

## Switching Back to Production Mode

When ready to switch back to production with email:

```bash
export ENVIRONMENT=production
export ENABLE_EMAIL_OTP=true
# Set SMTP credentials
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USERNAME=your-email@gmail.com
export SMTP_PASSWORD=your-app-password
export SMTP_FROM_EMAIL=your-email@gmail.com

# Restart server
```

Or update `.env.production`:
```bash
ENVIRONMENT=production
ENABLE_EMAIL_OTP=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
```

## Summary

✅ **Fixed**: `verify-otp` now accepts testing OTP (123456) even without calling `send-otp` first

✅ **Configuration**: Set `ENVIRONMENT=testing` and `ENABLE_EMAIL_OTP=false` to disable SMTP

✅ **Testing**: Use OTP `123456` for all email addresses in testing mode

✅ **Verification**: Test endpoints using curl or Swagger UI

## Quick Reference Commands

```bash
# Set environment variables
export ENVIRONMENT=testing
export TESTING_OTP=123456
export ENABLE_EMAIL_OTP=false

# Restart server (choose appropriate method)
sudo systemctl restart SERVICE_NAME
# OR
pm2 restart PROCESS_NAME
# OR
pkill -f uvicorn && uvicorn app.main:app --host 0.0.0.0 --port 8000

# Test endpoints
curl https://staffly.space/auth/debug/environment
curl -X POST "https://staffly.space/auth/send-otp?email=test@example.com"
curl -X POST "https://staffly.space/auth/verify-otp?email=test@example.com&otp=123456"
```
