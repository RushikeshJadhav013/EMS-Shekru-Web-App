#!/bin/bash

# Database Setup Script for EMS Application
# This script sets up the MySQL database and user

echo "=========================================="
echo "EMS Database Setup Script"
echo "=========================================="
echo ""

# Check if MySQL is running
echo "Checking MySQL status..."
if ! systemctl is-active --quiet mysql; then
    echo "MySQL is not running. Starting MySQL..."
    sudo systemctl start mysql
    sleep 2
fi

if systemctl is-active --quiet mysql; then
    echo "✓ MySQL is running"
else
    echo "✗ Failed to start MySQL"
    echo "Please start MySQL manually: sudo systemctl start mysql"
    exit 1
fi

echo ""
echo "=========================================="
echo "Creating Database and User"
echo "=========================================="
echo ""
echo "You will be prompted for the MySQL root password."
echo "Then the script will create:"
echo "  - Database: empl"
echo "  - User: staffly"
echo "  - Password: staff9612"
echo ""

# Create SQL commands file
cat > /tmp/setup_empl_db.sql << 'EOF'
-- Create database
CREATE DATABASE IF NOT EXISTS empl;

-- Create user (drop if exists to avoid errors)
DROP USER IF EXISTS 'staffly'@'localhost';
CREATE USER 'staffly'@'localhost' IDENTIFIED BY 'staff9612';

-- Grant privileges
GRANT ALL PRIVILEGES ON empl.* TO 'staffly'@'localhost';

-- Flush privileges
FLUSH PRIVILEGES;

-- Show databases
SHOW DATABASES;

-- Show grants
SHOW GRANTS FOR 'staffly'@'localhost';
EOF

# Execute SQL commands
echo "Executing SQL commands..."
sudo mysql -u root -p < /tmp/setup_empl_db.sql

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Database and user created successfully!"
    echo ""
    
    # Clean up
    rm /tmp/setup_empl_db.sql
    
    # Test connection
    echo "Testing connection..."
    if mysql -u staffly -pstaff9612 -e "USE empl; SELECT 'Connection successful!' as status;" 2>/dev/null; then
        echo "✓ Connection test passed!"
    else
        echo "✗ Connection test failed"
        echo "Please check the credentials"
        exit 1
    fi
    
    echo ""
    echo "=========================================="
    echo "Running Database Migrations"
    echo "=========================================="
    echo ""
    
    # Run employee_type migration
    if [ -f "Backend/add_employee_type_column.py" ]; then
        echo "Running employee_type migration..."
        python3 Backend/add_employee_type_column.py
    else
        echo "Migration script not found, skipping..."
    fi
    
    echo ""
    echo "=========================================="
    echo "Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Restart the backend server:"
    echo "   bash Backend/restart_backend.sh"
    echo ""
    echo "2. Or start manually:"
    echo "   cd Backend && uvicorn app.main:app --reload"
    echo ""
    echo "3. Test the application in your browser"
    echo ""
    
else
    echo ""
    echo "✗ Failed to create database and user"
    echo "Please check the error messages above"
    rm /tmp/setup_empl_db.sql
    exit 1
fi
