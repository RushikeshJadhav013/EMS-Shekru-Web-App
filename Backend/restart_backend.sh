#!/bin/bash

# Script to restart the backend server
# This will load the new export endpoint

echo "🔄 Restarting Backend Server..."
echo "================================"

# Check if running with systemd
if systemctl list-units --type=service | grep -q "staffly\|employee\|ems"; then
    echo "📋 Found systemd service"
    SERVICE_NAME=$(systemctl list-units --type=service | grep -E "staffly|employee|ems" | awk '{print $1}' | head -1)
    echo "Service: $SERVICE_NAME"
    sudo systemctl restart $SERVICE_NAME
    echo "✅ Service restarted"
    sudo systemctl status $SERVICE_NAME --no-pager
    exit 0
fi

# Check if running with PM2
if command -v pm2 &> /dev/null; then
    if pm2 list | grep -q "staffly\|employee\|ems\|backend"; then
        echo "📋 Found PM2 process"
        PM2_NAME=$(pm2 list | grep -E "staffly|employee|ems|backend" | awk '{print $2}' | head -1)
        echo "Process: $PM2_NAME"
        pm2 restart $PM2_NAME
        echo "✅ PM2 process restarted"
        pm2 list
        exit 0
    fi
fi

# Check if running with supervisor
if command -v supervisorctl &> /dev/null; then
    if supervisorctl status | grep -q "staffly\|employee\|ems"; then
        echo "📋 Found Supervisor process"
        SUPERVISOR_NAME=$(supervisorctl status | grep -E "staffly|employee|ems" | awk '{print $1}' | head -1)
        echo "Process: $SUPERVISOR_NAME"
        sudo supervisorctl restart $SUPERVISOR_NAME
        echo "✅ Supervisor process restarted"
        sudo supervisorctl status
        exit 0
    fi
fi

# Manual restart instructions
echo "⚠️  Could not detect process manager"
echo ""
echo "Please restart the backend manually:"
echo "1. Find the backend process:"
echo "   ps aux | grep uvicorn"
echo ""
echo "2. Kill the process:"
echo "   kill <PID>"
echo ""
echo "3. Start the backend:"
echo "   cd Backend"
echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "Or if using a specific deployment method, use that method to restart."
