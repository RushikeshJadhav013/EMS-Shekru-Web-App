# Environment-Based OTP System Setup Guide

## Overview

This system automatically detects the environment and adjusts OTP behavior accordingly:
- **Development**: Fixed OTP (123456), console output
- **Testing**: Fixed OTP (123456), console output  
- **Production**: Random OTP, email delivery

## Environment Configuration

### 1. Environment Variables

| Variable | Description | Default | Development | Testing | Production |
|----------|-------------|---------|-------------|---------|------------|
| `ENVIRONMENT` | Current environment | `development` | `development` | `testing` | `production` |
| `TESTING_OTP` | Fixed OTP for testing | `123456` | `123456` | `123456` | `123456` |
| `ENABLE_EMAIL_OTP` | Force email sending | `false` | `false` | `false` | `true` |
| `SMTP_HOST` | Email server host | - | - | - | Required |
| `SMTP_PORT` | Email server port | `587` | - | - | Required |
| `SMTP_USERNAME` | Email username | - | - | - | Required |
| `SMTP_PASSWORD` | Email password | - | - | - | Required |
| `SMTP_FROM_EMAIL` | From email address | - | - | - | Required |

### 2. Setup Instructions

#### Development Environment
```bash
# Copy development environment file
cp .env.development .env

# Or set manually
export ENVIRONMENT=development
export TESTING_OTP=123456
export ENABLE_EMAIL_OTP=false
```

#### Testing Environment
```bash
# Copy testing environment file
cp .env.testing .env

# Or set manually
export ENVIRONMENT=testing
export TESTING_OTP=123456
export ENABLE_EMAIL_OTP=false
```

#### Production Environment
```bash
# Copy production environment file and update credentials
cp .env.production .env

# Update these values:
# - DATABASE_URL (production database)
# - JWT_SECRET (strong secret)
# - SMTP_* settings (email configuration)
```

## OTP Behavior by Environment

### Development Environment
- **OTP Generation**: Always uses `123456`
- **OTP Display**: Shows in console with formatted output
- **Email Sending**: Disabled
- **Verification**: Accepts `123456` for any email
- **Debug Endpoints**: Available

### Testing Environment  
- **OTP Generation**: Always uses `123456`
- **OTP Display**: Shows in console with formatted output
- **Email Sending**: Disabled
- **Verification**: Accepts `123456` for any email
- **Debug Endpoints**: Available

### Production Environment
- **OTP Generation**: Random 6-digit number
- **OTP Display**: Logged only (not shown in console)
- **Email Sending**: Required and enabled
- **Verification**: Only accepts generated random OTP
- **Debug Endpoints**: Disabled (404)

## Testing Guide

### 1. Development Testing

#### Start Development Server
```bash
# Ensure development environment
export ENVIRONMENT=development

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Test OTP Flow
```bash
# 1. Send OTP (will show in console)
curl -X POST "http://localhost:8000/auth/send-otp?email=test@example.com"

# Console output:
# 🔧 [DEVELOPMENT] LOGIN OTP
# 📧 Email: test@example.com
# 🔢 OTP: 123456
# ⏰ Valid for: 5 minutes
# 🌍 Environment: development

# 2. Verify OTP (always 123456)
curl -X POST "http://localhost:8000/auth/verify-otp" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "otp": 123456}'
```

#### Debug Endpoints
```bash
# Check environment info
curl "http://localhost:8000/auth/debug/environment"

# Get OTP info for specific email
curl "http://localhost:8000/auth/debug/otp/test@example.com"

# Clear all OTPs
curl -X POST "http://localhost:8000/auth/debug/clear-otps"
```

### 2. Testing Environment Testing

#### Start Testing Server
```bash
# Ensure testing environment
export ENVIRONMENT=testing

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Test with Fixed OTP
```bash
# Send OTP (will show 123456 in console)
curl -X POST "http://localhost:8000/auth/send-otp?email=test@example.com"

# Verify with fixed OTP
curl -X POST "http://localhost:8000/auth/verify-otp" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "otp": 123456}'
```

### 3. Production Testing

#### Setup Production Environment
```bash
# Set production environment
export ENVIRONMENT=production

# Configure email settings
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USERNAME=your-email@gmail.com
export SMTP_PASSWORD=your-app-password
export SMTP_FROM_EMAIL=noreply@yourcompany.com
```

#### Test Email Configuration (in non-production first)
```bash
# Test email before going to production
export ENVIRONMENT=development
export ENABLE_EMAIL_OTP=true

# Test email sending
curl -X POST "http://localhost:8000/auth/debug/test-email"
```

#### Production OTP Flow
```bash
# Switch to production
export ENVIRONMENT=production

# Send OTP (will generate random OTP and send email)
curl -X POST "http://localhost:8000/auth/send-otp?email=user@example.com"

# Response:
# {
#   "message": "OTP sent successfully",
#   "environment": "production",
#   "otp_method": "email",
#   "expires_in_minutes": 5
# }

# Check email for actual OTP, then verify
curl -X POST "http://localhost:8000/auth/verify-otp" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "otp": 789123}'
```

## Deployment Configuration

### Netlify Frontend + Production Backend

#### Backend Deployment (Production)
```bash
# 1. Set production environment variables
export ENVIRONMENT=production
export DATABASE_URL=mysql+pymysql://user:pass@prod-host/empl_prod
export JWT_SECRET=your-strong-secret
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USERNAME=your-email@gmail.com
export SMTP_PASSWORD=your-app-password
export SMTP_FROM_EMAIL=noreply@yourcompany.com

# 2. Deploy backend (e.g., to Heroku, AWS, DigitalOcean)
# Ensure environment variables are set in deployment platform
```

#### Frontend Deployment (Netlify)
```bash
# 1. Update frontend API base URL
# In Frontend/.env.production:
VITE_API_BASE_URL=https://your-production-backend.com

# 2. Deploy to Netlify
npm run build
# Upload dist folder to Netlify
```

### Git Branch Strategy

#### Development Branch
```bash
# .env.development is used
# Fixed OTP for easy testing
# Console output enabled
```

#### Testing/Staging Branch  
```bash
# .env.testing is used
# Fixed OTP for automated testing
# Console output enabled
# Debug endpoints available
```

#### Main/Production Branch
```bash
# .env.production is used
# Random OTP generation
# Email sending required
# Debug endpoints disabled
# Strong security settings
```

## Verification Checklist

### Development Environment ✅
- [ ] OTP is always `123456`
- [ ] OTP appears in console
- [ ] Email sending is disabled
- [ ] Debug endpoints work
- [ ] Easy login for testing

### Testing Environment ✅
- [ ] OTP is always `123456`
- [ ] OTP appears in console
- [ ] Email sending is disabled
- [ ] Debug endpoints work
- [ ] Consistent for automated tests

### Production Environment ✅
- [ ] OTP is random 6-digit
- [ ] Email sending works
- [ ] Debug endpoints are disabled
- [ ] Console doesn't show OTP
- [ ] Strong security settings

## Troubleshooting

### Common Issues

#### OTP Not Working in Development
```bash
# Check environment
curl "http://localhost:8000/auth/debug/environment"

# Verify OTP info
curl "http://localhost:8000/auth/debug/otp/your-email@example.com"
```

#### Email Not Sending in Production
```bash
# Check email configuration
curl -X POST "http://localhost:8000/auth/debug/test-email"

# Verify SMTP settings in production
# - Check SMTP credentials
# - Verify app password for Gmail
# - Confirm firewall allows SMTP
```

#### Environment Detection Issues
```bash
# Check current environment
echo $ENVIRONMENT

# Verify settings are loaded
python -c "from app.core.config import settings; print(f'Environment: {settings.ENVIRONMENT}')"
```

## Security Notes

### Production Security
- Use strong JWT secret
- Configure SMTP with app passwords (not regular passwords)
- Enable SSL/TLS for database connections
- Monitor OTP generation logs
- Rotate secrets regularly

### Development Security
- Never commit `.env` files to Git
- Use different secrets for each environment
- Keep production credentials secure
- Test email configuration before production deployment

## Automated Testing

### Test Script
```bash
#!/bin/bash
# test_otp_environments.sh

echo "Testing OTP environments..."

# Test Development
export ENVIRONMENT=development
echo "Development: $(curl -s http://localhost:8000/auth/debug/environment)"

# Test Testing
export ENVIRONMENT=testing  
echo "Testing: $(curl -s http://localhost:8000/auth/debug/environment)"

# Verify OTP generation
curl -X POST "http://localhost:8000/auth/send-otp?email=test@example.com"

echo "Environment tests completed!"
```

This comprehensive setup ensures your OTP system works correctly across all environments without manual code changes!
