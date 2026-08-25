"""
Database migration script to create salary-related tables
Run this script to add salary tables to the database
"""
import sys
import os

# Add the Backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.database import engine, SessionLocal

def create_salary_tables():
    """Create salary-related tables if they don't exist"""
    
    # SQL statements to create tables
    create_employee_salaries = """
    CREATE TABLE IF NOT EXISTS employee_salaries (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL UNIQUE,
        basic_annual FLOAT DEFAULT 0.0,
        hra_annual FLOAT DEFAULT 0.0,
        special_allowance_annual FLOAT DEFAULT 0.0,
        conveyance_annual FLOAT DEFAULT 0.0,
        medical_allowance_annual FLOAT DEFAULT 0.0,
        other_allowance_annual FLOAT DEFAULT 0.0,
        professional_tax_annual FLOAT DEFAULT 0.0,
        other_deduction_annual FLOAT DEFAULT 0.0,
        pf_annual FLOAT DEFAULT 0.0,
        pan_number VARCHAR(20),
        uan_number VARCHAR(20),
        pf_no VARCHAR(30) NULL UNIQUE,
        bank_name VARCHAR(100),
        bank_account VARCHAR(50),
        ifsc_code VARCHAR(20),
        variable_pay FLOAT DEFAULT 0.0,
        working_days_per_month INT DEFAULT 22,
        payment_mode VARCHAR(50) DEFAULT 'Bank Transfer',
        is_active BOOLEAN DEFAULT TRUE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        INDEX idx_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    
    create_salary_increments = """
    CREATE TABLE IF NOT EXISTS salary_increments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        previous_salary FLOAT NOT NULL,
        increment_amount FLOAT NOT NULL,
        new_salary FLOAT NOT NULL,
        increment_percentage FLOAT,
        effective_date DATETIME NOT NULL,
        reason TEXT,
        approved_by INT,
        letter_sent BOOLEAN DEFAULT FALSE,
        letter_sent_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (approved_by) REFERENCES users(user_id) ON DELETE SET NULL,
        INDEX idx_user_id (user_id),
        INDEX idx_effective_date (effective_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    
    create_salary_slip_history = """
    CREATE TABLE IF NOT EXISTS salary_slip_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        month INT NOT NULL,
        year INT NOT NULL,
        gross_salary FLOAT NOT NULL,
        total_deductions FLOAT NOT NULL,
        net_salary FLOAT NOT NULL,
        optional_deduction_1_label VARCHAR(120) NULL,
        optional_deduction_1_amount FLOAT NULL,
        optional_deduction_2_label VARCHAR(120) NULL,
        optional_deduction_2_amount FLOAT NULL,
        optional_deduction_3_label VARCHAR(120) NULL,
        optional_deduction_3_amount FLOAT NULL,
        optional_deduction_4_label VARCHAR(120) NULL,
        optional_deduction_4_amount FLOAT NULL,
        manual_leave_days FLOAT DEFAULT 0,
        manual_leave_amount FLOAT DEFAULT 0,
        generated_by INT,
        generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        email_sent BOOLEAN DEFAULT FALSE,
        email_sent_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (generated_by) REFERENCES users(user_id) ON DELETE SET NULL,
        INDEX idx_user_id (user_id),
        INDEX idx_month_year (month, year)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    
    try:
        with engine.begin() as conn:
            print("Creating employee_salaries table...")
            conn.execute(text(create_employee_salaries))
            print("✅ employee_salaries table created/verified")
            
            print("Creating salary_increments table...")
            conn.execute(text(create_salary_increments))
            print("✅ salary_increments table created/verified")
            
            print("Creating salary_slip_history table...")
            conn.execute(text(create_salary_slip_history))
            print("✅ salary_slip_history table created/verified")
            
        print("\n✅ All salary tables created successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error creating tables: {str(e)}")
        return False


def verify_tables():
    """Verify that all salary tables exist"""
    tables = ['employee_salaries', 'salary_increments', 'salary_slip_history']
    
    try:
        with engine.begin() as conn:
            for table in tables:
                result = conn.execute(text(f"""
                    SELECT COUNT(*) as cnt
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = '{table}'
                """))
                row = result.first()
                exists = bool(row[0] if row else 0)
                status = "✅" if exists else "❌"
                print(f"{status} Table '{table}': {'exists' if exists else 'NOT FOUND'}")
        
        return True
    except Exception as e:
        print(f"Error verifying tables: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Salary Tables Migration Script")
    print("=" * 50)
    
    print("\n📋 Creating salary tables...")
    create_salary_tables()
    
    print("\n📋 Verifying tables...")
    verify_tables()
    
    print("\n" + "=" * 50)
    print("Migration complete!")
    print("=" * 50)
