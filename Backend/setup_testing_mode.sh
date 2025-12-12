#!/bin/bash

# Script to switch Staffly backend from production SMTP to testing mode with fixed OTP

set -e

echo "=========================================="
echo "  Staffly Testing Mode Setup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Navigate to backend directory
cd "$(dirname "$0")"
BACKEND_DIR=$(pwd)

echo "📁 Backend directory: $BACKEND_DIR"
echo ""

# Check if .env.production exists
ENV_FILE="$BACKEND_DIR/.env.production"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠️  .env.production not found. Creating it...${NC}"
    touch "$ENV_FILE"
fi

# Backup existing .env.production
BACKUP_FILE="$BACKEND_DIR/.env.production.backup.$(date +%Y%m%d_%H%M%S)"
cp "$ENV_FILE" "$BACKUP_FILE" 2>/dev/null || echo "# Backup file" > "$BACKUP_FILE"
echo "💾 Backup created: $BACKUP_FILE"
echo ""

# Update .env.production with testing configuration
echo "🔧 Updating environment configuration..."

# Read existing file and update/add required variables
if grep -q "^ENVIRONMENT=" "$ENV_FILE"; then
    sed -i 's/^ENVIRONMENT=.*/ENVIRONMENT=testing/' "$ENV_FILE"
else
    echo "ENVIRONMENT=testing" >> "$ENV_FILE"
fi

if grep -q "^TESTING_OTP=" "$ENV_FILE"; then
    sed -i 's/^TESTING_OTP=.*/TESTING_OTP=123456/' "$ENV_FILE"
else
    echo "TESTING_OTP=123456" >> "$ENV_FILE"
fi

if grep -q "^ENABLE_EMAIL_OTP=" "$ENV_FILE"; then
    sed -i 's/^ENABLE_EMAIL_OTP=.*/ENABLE_EMAIL_OTP=false/' "$ENV_FILE"
else
    echo "ENABLE_EMAIL_OTP=false" >> "$ENV_FILE"
fi

echo -e "${GREEN}✅ Configuration updated${NC}"
echo ""

# Display current configuration
echo "📋 Current Configuration:"
echo "------------------------"
grep -E "^ENVIRONMENT=|^TESTING_OTP=|^ENABLE_EMAIL_OTP=" "$ENV_FILE" || echo "No matching variables found"
echo ""

# Export variables for current session
export ENVIRONMENT=testing
export TESTING_OTP=123456
export ENABLE_EMAIL_OTP=false

echo "🔍 Verifying configuration..."
python3 << EOF
import sys
sys.path.insert(0, '$BACKEND_DIR')
from app.core.config import settings

print(f"Environment: {settings.ENVIRONMENT}")
print(f"Testing OTP: {settings.TESTING_OTP}")
print(f"Use Fixed OTP: {settings.should_use_fixed_otp}")
print(f"Send Email: {settings.should_send_email}")
print(f"Enable Email OTP: {settings.ENABLE_EMAIL_OTP}")

if settings.ENVIRONMENT.lower() == "testing" and not settings.should_send_email:
    print("\n✅ Configuration is correct!")
    sys.exit(0)
else:
    print("\n❌ Configuration mismatch!")
    sys.exit(1)
EOF

CONFIG_OK=$?

if [ $CONFIG_OK -ne 0 ]; then
    echo -e "${RED}❌ Configuration verification failed${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo "  Server Restart Options"
echo "=========================================="
echo ""

# Detect process manager
RESTART_METHOD=""

# Check for systemd
if systemctl list-units --type=service 2>/dev/null | grep -qE "staffly|employee|ems|backend"; then
    SERVICE_NAME=$(systemctl list-units --type=service 2>/dev/null | grep -E "staffly|employee|ems|backend" | awk '{print $1}' | head -1)
    echo "📋 Found systemd service: $SERVICE_NAME"
    RESTART_METHOD="systemd"
    RESTART_CMD="sudo systemctl restart $SERVICE_NAME"
elif command -v pm2 &> /dev/null && pm2 list 2>/dev/null | grep -qE "staffly|employee|ems|backend"; then
    PM2_NAME=$(pm2 list 2>/dev/null | grep -E "staffly|employee|ems|backend" | awk '{print $2}' | head -1)
    echo "📋 Found PM2 process: $PM2_NAME"
    RESTART_METHOD="pm2"
    RESTART_CMD="pm2 restart $PM2_NAME"
elif command -v supervisorctl &> /dev/null && supervisorctl status 2>/dev/null | grep -qE "staffly|employee|ems|backend"; then
    SUPERVISOR_NAME=$(supervisorctl status 2>/dev/null | grep -E "staffly|employee|ems|backend" | awk '{print $1}' | head -1)
    echo "📋 Found Supervisor process: $SUPERVISOR_NAME"
    RESTART_METHOD="supervisor"
    RESTART_CMD="sudo supervisorctl restart $SUPERVISOR_NAME"
else
    echo "⚠️  No process manager detected"
    RESTART_METHOD="manual"
fi

echo ""
echo "Choose restart method:"
echo "1) Auto-detect ($RESTART_METHOD)"
echo "2) systemd"
echo "3) PM2"
echo "4) Supervisor"
echo "5) Manual (I'll restart myself)"
echo ""
read -p "Enter choice [1-5] (default: 1): " choice
choice=${choice:-1}

case $choice in
    1)
        if [ "$RESTART_METHOD" != "manual" ]; then
            echo ""
            echo "🔄 Restarting server using $RESTART_METHOD..."
            eval $RESTART_CMD
            echo -e "${GREEN}✅ Server restarted${NC}"
        else
            echo ""
            echo "⚠️  Please restart the server manually:"
            echo "   cd $BACKEND_DIR"
            echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
        fi
        ;;
    2)
        read -p "Enter systemd service name: " service_name
        echo ""
        echo "🔄 Restarting systemd service: $service_name..."
        sudo systemctl restart $service_name
        echo -e "${GREEN}✅ Server restarted${NC}"
        sudo systemctl status $service_name --no-pager
        ;;
    3)
        read -p "Enter PM2 process name: " pm2_name
        echo ""
        echo "🔄 Restarting PM2 process: $pm2_name..."
        pm2 restart $pm2_name
        echo -e "${GREEN}✅ Server restarted${NC}"
        pm2 list
        ;;
    4)
        read -p "Enter Supervisor process name: " supervisor_name
        echo ""
        echo "🔄 Restarting Supervisor process: $supervisor_name..."
        sudo supervisorctl restart $supervisor_name
        echo -e "${GREEN}✅ Server restarted${NC}"
        sudo supervisorctl status
        ;;
    5)
        echo ""
        echo "⚠️  Please restart the server manually:"
        echo "   cd $BACKEND_DIR"
        echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "  Testing Instructions"
echo "=========================================="
echo ""
echo "1. Test environment info:"
echo "   curl https://staffly.space/auth/debug/environment"
echo ""
echo "2. Send OTP (should NOT send email):"
echo "   curl -X POST \"https://staffly.space/auth/send-otp?email=test@example.com\""
echo ""
echo "3. Verify OTP with fixed code (123456):"
echo "   curl -X POST \"https://staffly.space/auth/verify-otp?email=test@example.com&otp=123456\""
echo ""
echo "4. Test in Swagger UI:"
echo "   https://staffly.space/docs"
echo ""
echo "=========================================="
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "📝 Summary:"
echo "  - Environment: testing"
echo "  - Fixed OTP: 123456"
echo "  - Email sending: DISABLED"
echo "  - Backup saved: $BACKUP_FILE"
echo ""
echo "💡 Use OTP '123456' for any email address in testing mode"
echo ""
