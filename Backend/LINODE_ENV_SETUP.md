# Linode Server: Environment Files Configuration Guide

## Overview
Your Linode server uses separate environment files (`.env.development`, `.env.testing`, `.env.production`) and the `deploy.sh` script to switch between environments. This guide explains what changes need to be made to `.env.testing` file on your Linode server.

---

## What Needs to be Changed in `.env.testing` File

### Current `.env.testing` File (Example)
```bash
# Testing Environment Configuration
ENVIRONMENT=testing

# Database Configuration (use test database)
DATABASE_URL=mysql+pymysql://root:root@localhost/empl_test

# JWT Configuration
JWT_SECRET=test-secret-key
JWT_ALGORITHM=HS256

# OTP Configuration
OTP_EXPIRY_MINUTES=5
TESTING_OTP=123456
ENABLE_EMAIL_OTP=false

# Email Configuration (disabled for testing)
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
```

### Required Changes for `.env.testing` on Linode Server

**Important**: You need to update `.env.testing` to use your **production database** (not test database) and ensure email is disabled:

```bash
# Testing Environment Configuration
ENVIRONMENT=testing

# Database Configuration (USE PRODUCTION DATABASE)
DATABASE_URL=mysql+pymysql://staffly:staff9612@localhost/empl

# JWT Configuration (use production secret)
JWT_SECRET=supersecretjwtkey
JWT_ALGORITHM=HS256

# OTP Configuration
OTP_EXPIRY_SECONDS=120
TESTING_OTP=123456
ENABLE_EMAIL_OTP=false

# Email Configuration (DISABLED - leave empty)
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
```

### Key Changes:
1. ✅ `ENVIRONMENT=testing` (already correct)
2. ✅ `TESTING_OTP=123456` (already correct)
3. ✅ `ENABLE_EMAIL_OTP=false` (already correct)
4. ⚠️ **Change `DATABASE_URL`** to production database: `mysql+pymysql://staffly:staff9612@localhost/empl`
5. ⚠️ **Change `OTP_EXPIRY_MINUTES`** to `OTP_EXPIRY_SECONDS=120` (to match config.py)
6. ⚠️ **Update `JWT_SECRET`** to match production (if different)

---

## Step-by-Step Instructions for Linode Server

### Step 1: SSH into Linode Server
```bash
ssh root@staffly.space
# OR
ssh ubuntu@staffly.space
```

### Step 2: Navigate to Backend Directory
```bash
cd /var/www/EMS-Shekru-Web-App/Backend
# OR wherever your backend is located
```

### Step 3: Backup Current `.env.testing` File
```bash
cp .env.testing .env.testing.backup.$(date +%Y%m%d_%H%M%S)
```

### Step 4: Edit `.env.testing` File
```bash
nano .env.testing
# OR
vim .env.testing
```

### Step 5: Update the File with Correct Values

**Copy this complete configuration:**

```bash
# Testing Environment Configuration
ENVIRONMENT=testing

# Database Configuration (PRODUCTION DATABASE)
DATABASE_URL=mysql+pymysql://staffly:staff9612@localhost/empl

# JWT Configuration
JWT_SECRET=supersecretjwtkey
JWT_ALGORITHM=HS256

# OTP Configuration
OTP_EXPIRY_SECONDS=120
TESTING_OTP=123456
ENABLE_EMAIL_OTP=false

# Email Configuration (DISABLED for testing)
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
```

**Save and exit:**
- **nano**: `Ctrl+X`, then `Y`, then `Enter`
- **vim**: Press `Esc`, type `:wq`, then `Enter`

### Step 6: Verify the Configuration
```bash
# Check the file contents
cat .env.testing | grep -E "ENVIRONMENT|TESTING_OTP|ENABLE_EMAIL_OTP|DATABASE_URL"

# Should show:
# ENVIRONMENT=testing
# DATABASE_URL=mysql+pymysql://staffly:staff9612@localhost/empl
# TESTING_OTP=123456
# ENABLE_EMAIL_OTP=false
```

### Step 7: Deploy Using Testing Environment

You have **two options**:

#### Option A: Use Deploy Script (Recommended)
```bash
# This will copy .env.testing to .env and start the server
./deploy.sh testing
```

#### Option B: Manual Deployment
```bash
# Copy .env.testing to .env
cp .env.testing .env

# Load environment variables
source .env

# Restart your server (choose appropriate method)
# For systemd:
sudo systemctl restart staffly-backend

# For PM2:
pm2 restart backend

# For Supervisor:
sudo supervisorctl restart backend:*
```

### Step 8: Verify Server is Running in Testing Mode
```bash
# Test environment endpoint
curl https://staffly.space/auth/debug/environment

# Expected response:
# {
#   "environment": "testing",
#   "should_use_fixed_otp": true,
#   "should_send_email": false,
#   "testing_otp": "123456",
#   "enable_email_otp": false,
#   "active_otps": 0
# }
```

---

## Complete `.env.testing` Template for Linode Server

Here's the complete template you should use:

```bash
# ============================================
# Testing Environment Configuration
# For Linode Production Server
# ============================================

# Environment
ENVIRONMENT=testing

# Database Configuration
# IMPORTANT: Use production database, not test database
DATABASE_URL=mysql+pymysql://staffly:staff9612@localhost/empl

# JWT Configuration
JWT_SECRET=supersecretjwtkey
JWT_ALGORITHM=HS256

# OTP Configuration
OTP_EXPIRY_SECONDS=120
TESTING_OTP=123456
ENABLE_EMAIL_OTP=false

# Email Configuration (DISABLED - no SMTP credentials needed)
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
```

---

## Comparison: `.env.testing` vs `.env.production`

| Setting | `.env.testing` | `.env.production` |
|---------|---------------|-------------------|
| `ENVIRONMENT` | `testing` | `production` |
| `DATABASE_URL` | Same as production | `mysql+pymysql://staffly:staff9612@localhost/empl` |
| `TESTING_OTP` | `123456` | Not used (random OTP) |
| `ENABLE_EMAIL_OTP` | `false` | `true` |
| `SMTP_HOST` | Empty | `smtp.gmail.com` |
| `SMTP_USERNAME` | Empty | Your Gmail |
| `SMTP_PASSWORD` | Empty | Your Gmail App Password |

---

## Quick Setup Script for Linode Server

Create and run this script on your Linode server:

```bash
#!/bin/bash
# Save as: update_env_testing.sh

cd /path/to/Backend  # Change to your backend path

# Backup
cp .env.testing .env.testing.backup.$(date +%Y%m%d_%H%M%S)

# Create new .env.testing
cat > .env.testing << 'EOF'
ENVIRONMENT=testing
DATABASE_URL=mysql+pymysql://staffly:staff9612@localhost/empl
JWT_SECRET=supersecretjwtkey
JWT_ALGORITHM=HS256
OTP_EXPIRY_SECONDS=120
TESTING_OTP=123456
ENABLE_EMAIL_OTP=false
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
EOF

echo "✅ .env.testing updated"
echo ""
echo "📋 Updated configuration:"
cat .env.testing
echo ""
echo "🚀 Now deploy with: ./deploy.sh testing"
```

---

## Important Notes

1. **Database**: Use **production database** (`empl`), not test database (`empl_test`)
   - You want to test with real data, not a separate test database

2. **Email Disabled**: `ENABLE_EMAIL_OTP=false` ensures no emails are sent
   - OTP will be logged to console/server logs instead

3. **Fixed OTP**: `TESTING_OTP=123456` means all users can use `123456` as OTP

4. **Deploy Script**: Use `./deploy.sh testing` to switch to testing mode
   - This copies `.env.testing` to `.env` and starts the server

5. **Server Restart**: After updating `.env.testing`, you need to:
   - Either run `./deploy.sh testing`
   - Or manually copy `.env.testing` to `.env` and restart server

---

## Verification Checklist

After making changes, verify:

- [ ] `.env.testing` has `ENVIRONMENT=testing`
- [ ] `.env.testing` has `TESTING_OTP=123456`
- [ ] `.env.testing` has `ENABLE_EMAIL_OTP=false`
- [ ] `.env.testing` has production `DATABASE_URL`
- [ ] Deployed using `./deploy.sh testing` OR copied `.env.testing` to `.env`
- [ ] Server restarted
- [ ] `curl https://staffly.space/auth/debug/environment` shows `"environment": "testing"`
- [ ] `send-otp` does NOT send email (check logs)
- [ ] `verify-otp` works with OTP `123456`

---

## Troubleshooting

### Issue: Still Using Production Database
**Solution**: Make sure `DATABASE_URL` in `.env.testing` matches production:
```bash
DATABASE_URL=mysql+pymysql://staffly:staff9612@localhost/empl
```

### Issue: Still Sending Emails
**Solution**: Verify `ENABLE_EMAIL_OTP=false` in `.env.testing`:
```bash
grep ENABLE_EMAIL_OTP .env.testing
# Should show: ENABLE_EMAIL_OTP=false
```

### Issue: OTP Not Working
**Solution**: 
1. Check `TESTING_OTP=123456` is set
2. Verify code changes are deployed (verify_otp function fix)
3. Check server logs for OTP verification attempts

### Issue: Wrong Environment Detected
**Solution**: Make sure `.env.testing` was copied to `.env`:
```bash
# Check current .env file
cat .env | grep ENVIRONMENT
# Should show: ENVIRONMENT=testing

# If not, copy it:
cp .env.testing .env
# Then restart server
```

---

## Summary

**What to change in `.env.testing` on Linode server:**

1. ✅ Keep: `ENVIRONMENT=testing`
2. ✅ Keep: `TESTING_OTP=123456`
3. ✅ Keep: `ENABLE_EMAIL_OTP=false`
4. ⚠️ **Change**: `DATABASE_URL` to production database
5. ⚠️ **Change**: `OTP_EXPIRY_MINUTES` to `OTP_EXPIRY_SECONDS=120`
6. ⚠️ **Update**: `JWT_SECRET` to match production (if different)
7. ✅ Keep: SMTP fields empty

**Then deploy:**
```bash
./deploy.sh testing
```

**Or manually:**
```bash
cp .env.testing .env
# Restart server
```
