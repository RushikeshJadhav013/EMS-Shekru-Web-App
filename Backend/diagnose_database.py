#!/usr/bin/env python3
"""
Database Connection Diagnostic Tool

This script helps diagnose database connection issues.
Run this to identify the problem with employee fetching.

Usage:
    python3 Backend/diagnose_database.py
"""

import sys
import os

# Add the Backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_mysql_connection():
    """Test MySQL connection"""
    print("\n" + "="*60)
    print("Testing MySQL Connection")
    print("="*60)
    
    try:
        import pymysql
        print("✓ pymysql module is installed")
    except ImportError:
        print("✗ pymysql module is NOT installed")
        print("  Install with: pip install pymysql")
        return False
    
    try:
        from app.core.config import settings
        print(f"✓ Configuration loaded")
        print(f"  Database URL: {settings.DATABASE_URL}")
        
        # Parse the connection string
        # Format: mysql+pymysql://user:password@host/database
        import re
        match = re.match(r'mysql\+pymysql://([^:]+):([^@]+)@([^/]+)/(.+)', settings.DATABASE_URL)
        if match:
            user, password, host, database = match.groups()
            print(f"  User: {user}")
            print(f"  Host: {host}")
            print(f"  Database: {database}")
            
            # Try to connect
            try:
                connection = pymysql.connect(
                    host=host.split(':')[0],  # Remove port if present
                    user=user,
                    password=password,
                    database=database
                )
                print("✓ Successfully connected to MySQL!")
                
                # Test query
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM users")
                    count = cursor.fetchone()[0]
                    print(f"✓ Found {count} users in database")
                
                connection.close()
                return True
                
            except pymysql.err.OperationalError as e:
                print(f"✗ MySQL Connection Failed: {e}")
                print("\nPossible solutions:")
                print("1. Check if MySQL server is running:")
                print("   sudo systemctl status mysql")
                print("2. Start MySQL if not running:")
                print("   sudo systemctl start mysql")
                print("3. Create the database and user:")
                print("   sudo mysql -u root -p")
                print("   CREATE DATABASE IF NOT EXISTS empl;")
                print(f"   CREATE USER IF NOT EXISTS '{user}'@'localhost' IDENTIFIED BY '{password}';")
                print(f"   GRANT ALL PRIVILEGES ON empl.* TO '{user}'@'localhost';")
                print("   FLUSH PRIVILEGES;")
                print("   EXIT;")
                return False
                
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_sqlalchemy_connection():
    """Test SQLAlchemy connection"""
    print("\n" + "="*60)
    print("Testing SQLAlchemy Connection")
    print("="*60)
    
    try:
        from sqlalchemy import create_engine, text
        from app.core.config import settings
        
        print("✓ SQLAlchemy imported successfully")
        
        engine = create_engine(settings.DATABASE_URL)
        print("✓ Engine created")
        
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✓ Test query executed successfully")
            
            # Check if users table exists
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'users'
            """))
            table_exists = result.fetchone()[0]
            
            if table_exists:
                print("✓ 'users' table exists")
                
                # Check for employee_type column
                result = connection.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'users' 
                    AND column_name = 'employee_type'
                """))
                column_exists = result.fetchone()[0]
                
                if column_exists:
                    print("✓ 'employee_type' column exists")
                else:
                    print("✗ 'employee_type' column is MISSING")
                    print("  Run: python3 Backend/add_employee_type_column.py")
                    
            else:
                print("✗ 'users' table does NOT exist")
                print("  You need to run database migrations to create tables")
        
        return True
        
    except Exception as e:
        print(f"✗ SQLAlchemy connection failed: {e}")
        return False

def test_crud_operations():
    """Test CRUD operations"""
    print("\n" + "="*60)
    print("Testing CRUD Operations")
    print("="*60)
    
    try:
        from app.db.database import SessionLocal
        from app.crud.user_crud import list_users
        
        print("✓ Imports successful")
        
        db = SessionLocal()
        print("✓ Database session created")
        
        users = list_users(db)
        print(f"✓ Successfully fetched {len(users)} users")
        
        if users:
            print("\nSample users:")
            for user in users[:3]:
                print(f"  - {user.name} ({user.email}) - {user.role}")
        else:
            print("  No users found in database")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ CRUD operation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoint():
    """Test the API endpoint"""
    print("\n" + "="*60)
    print("Testing API Endpoint")
    print("="*60)
    
    try:
        import requests
        
        print("Testing GET /employees endpoint...")
        response = requests.get("https://staffly.space/employees", timeout=5)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Endpoint returned {len(data)} employees")
            return True
        else:
            print(f"✗ Endpoint returned error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to backend server")
        print("  Make sure the backend is running:")
        print("  cd Backend && uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"✗ API test failed: {e}")
        return False

def main():
    """Run all diagnostic tests"""
    print("\n" + "="*60)
    print("DATABASE CONNECTION DIAGNOSTIC TOOL")
    print("="*60)
    
    results = {
        "MySQL Connection": test_mysql_connection(),
        "SQLAlchemy Connection": test_sqlalchemy_connection(),
        "CRUD Operations": test_crud_operations(),
        "API Endpoint": test_api_endpoint(),
    }
    
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ All tests passed! The system should be working correctly.")
    else:
        print("\n✗ Some tests failed. Please follow the suggestions above to fix the issues.")
        print("\nQuick Fix Steps:")
        print("1. sudo systemctl start mysql")
        print("2. sudo mysql -u root -p")
        print("3. Run the SQL commands shown above")
        print("4. python3 Backend/add_employee_type_column.py")
        print("5. Restart the backend server")
    
    print("="*60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
