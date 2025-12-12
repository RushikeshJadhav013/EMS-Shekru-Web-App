# Quick Reference: Linode Server `.env.testing` Changes

## What to Change in `.env.testing` File

### Current (Wrong) Configuration:
```bash
DATABASE_URL=mysql+pymysql://root:root@localhost/empl_test  # ❌ Wrong - test database
OTP_EXPIRY_MINUTES=5  # ❌ Wrong - should be OTP_EXPIRY_SECONDS
```

### Required (Correct) Configuration:
```bash
DATABASE_URL=mysql+pymysql://staffly:staff9612@localhost/empl  # ✅ Production database
OTP_EXPIRY_SECONDS=120  # ✅ Matches config.py
```

---

## Complete `.env.testing` File for Linode Server

```bash
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
```

---

## Quick Commands for Linode Server

```bash
# 1. SSH into server
ssh root@staffly.space

# 2. Navigate to backend
cd /path/to/Backend

# 3. Backup current file
cp .env.testing .env.testing.backup

# 4. Edit file
nano .env.testing

# 5. Update DATABASE_URL and OTP_EXPIRY_SECONDS (see above)

# 6. Deploy
./deploy.sh testing

# 7. Verify
curl https://staffly.space/auth/debug/environment
```

---

## Key Points

✅ **Keep these as-is:**
- `ENVIRONMENT=testing`
- `TESTING_OTP=123456`
- `ENABLE_EMAIL_OTP=false`

⚠️ **Change these:**
- `DATABASE_URL` → Use production database (`empl`, not `empl_test`)
- `OTP_EXPIRY_MINUTES` → Change to `OTP_EXPIRY_SECONDS=120`

✅ **Leave SMTP empty:**
- All SMTP fields should be empty (no email sending)

---

## After Changes

1. Run: `./deploy.sh testing`
2. Or manually: `cp .env.testing .env` then restart server
3. Test: `curl https://staffly.space/auth/debug/environment`
