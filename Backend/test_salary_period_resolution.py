"""
Test script to verify historical salary resolution, increment audit tracking, and frozen slip components.
"""
import sys
import os
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
import app.main  # Ensures all models and relationships are registered
from app.db.models.user import User
from app.db.models.salary import EmployeeSalary, EmployeeSalaryHistory, SalaryIncrement, SalarySlipHistory
from app.crud.salary_crud import (
    create_employee_salary_from_ctc,
    create_salary_increment,
    get_salary_structure_for_period,
    create_salary_slip_history,
    get_salary_slip_history,
)
from app.schemas.salary_schema import EmployeeSalaryCTCCreate, SalaryIncrementCreate

def run_tests():
    db = SessionLocal()
    try:
        print("=== 1. Setting up test user and baseline salary ===")
        # Find or create a test user
        test_email = "test_increment_flow@example.com"
        user = db.query(User).filter(User.email == test_email).first()
        if not user:
            user = User(
                name="Test Employee",
                email=test_email,
                role="employee",
                is_active=True,
                joining_date=date(2026, 1, 1),
                company_id=1,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.joining_date = date(2026, 1, 1)
            db.commit()

        # Clean any old test records for this user
        db.query(SalarySlipHistory).filter(SalarySlipHistory.user_id == user.user_id).delete()
        db.query(SalaryIncrement).filter(SalaryIncrement.user_id == user.user_id).delete()
        db.query(EmployeeSalaryHistory).filter(EmployeeSalaryHistory.user_id == user.user_id).delete()
        db.query(EmployeeSalary).filter(EmployeeSalary.user_id == user.user_id).delete()
        db.commit()

        # Initial salary (6 LPA) created on 2026-01-01
        initial_salary_data = EmployeeSalaryCTCCreate(
            user_id=user.user_id,
            package_ctc_annual=600000.0,
            variable_pay_type="none",
            variable_pay_value=0.0,
        )
        salary = create_employee_salary_from_ctc(db, initial_salary_data)
        salary.created_at = datetime(2026, 1, 1, 10, 0, 0)
        db.commit()
        print(f"Created baseline salary: CTC={salary.package_ctc_annual}, Basic={salary.basic_annual}")

        # === TEST 2: Pre-joining increment validation ===
        print("\n=== 2. Testing Pre-Joining Increment Validation ===")
        try:
            bad_increment = SalaryIncrementCreate(
                user_id=user.user_id,
                increment_ctc_annual=100000.0,
                effective_date=datetime(2025, 12, 1, 0, 0, 0), # Before joining 2026-01-01
            )
            create_salary_increment(db, bad_increment, approved_by=1, approved_by_name="Admin", approved_by_role="admin")
            print("❌ FAILED: Pre-joining increment should have been rejected!")
            return False
        except ValueError as e:
            print(f"✅ PASSED: Pre-joining increment rejected correctly: {e}")

        # === TEST 3: Apply increment in October 2026 with Admin audit info ===
        print("\n=== 3. Applying Increment in October 2026 with Admin Audit ===")
        increment_data = SalaryIncrementCreate(
            user_id=user.user_id,
            increment_ctc_annual=300000.0, # 6L -> 9L
            effective_date=datetime(2026, 10, 1, 0, 0, 0),
            reason="Annual Performance Review",
        )
        inc = create_salary_increment(
            db,
            increment_data,
            approved_by=1,
            approved_by_name="HR Manager",
            approved_by_role="hr",
        )
        assert inc.effective_month == 10, f"Expected effective_month=10, got {inc.effective_month}"
        assert inc.effective_year == 2026, f"Expected effective_year=2026, got {inc.effective_year}"
        assert inc.approved_by_name == "HR Manager", f"Expected approved_by_name='HR Manager', got {inc.approved_by_name}"
        assert inc.approved_by_role == "hr", f"Expected approved_by_role='hr', got {inc.approved_by_role}"
        print(f"✅ PASSED: Increment created: previous_ctc={inc.previous_ctc_annual}, new_ctc={inc.new_ctc_annual}")
        print(f"   Audit recorded: approved_by_name={inc.approved_by_name}, approved_by_role={inc.approved_by_role}, month={inc.effective_month}, year={inc.effective_year}")

        # === TEST 4: Chronological increment validation ===
        print("\n=== 4. Testing Chronological Increment Validation ===")
        try:
            out_of_order = SalaryIncrementCreate(
                user_id=user.user_id,
                increment_ctc_annual=50000.0,
                effective_date=datetime(2026, 6, 1, 0, 0, 0), # Before existing 2026-10-01
            )
            create_salary_increment(db, out_of_order, approved_by=1, approved_by_name="Admin", approved_by_role="admin")
            print("❌ FAILED: Out-of-order increment should have been rejected!")
            return False
        except ValueError as e:
            print(f"✅ PASSED: Out-of-order increment rejected correctly: {e}")

        # === TEST 5: Period resolution for March 2026 vs October 2026 ===
        print("\n=== 5. Testing Period-Based Salary Structure Resolution ===")
        # March 2026 slip request (MUST be the old 6 LPA structure)
        march_salary = get_salary_structure_for_period(db, user.user_id, month=3, year=2026)
        assert march_salary is not None, "March salary should not be None"
        print(f"March 2026 Salary Structure: Type={type(march_salary).__name__}, CTC={march_salary.package_ctc_annual}, Basic={march_salary.basic_annual}")
        assert abs(float(march_salary.package_ctc_annual) - 600000.0) < 0.01, f"Expected March CTC 600000, got {march_salary.package_ctc_annual}"

        # October 2026 slip request (MUST be the new 9 LPA structure)
        oct_salary = get_salary_structure_for_period(db, user.user_id, month=10, year=2026)
        assert oct_salary is not None, "October salary should not be None"
        print(f"October 2026 Salary Structure: Type={type(oct_salary).__name__}, CTC={oct_salary.package_ctc_annual}, Basic={oct_salary.basic_annual}")
        assert abs(float(oct_salary.package_ctc_annual) - 900000.0) < 0.01, f"Expected October CTC 900000, got {oct_salary.package_ctc_annual}"

        print("✅ PASSED: Historical salary resolution correctly returns old salary for March 2026 and new salary for October 2026!")

        # === TEST 6: Frozen salary slip components in salary_slip_history ===
        print("\n=== 6. Testing Frozen Salary Slip Components in DB ===")
        basic_march = round(march_salary.basic_annual / 12, 2)
        hra_march = round(march_salary.hra_annual / 12, 2)
        slip_hist = create_salary_slip_history(
            db,
            user_id=user.user_id,
            month=3,
            year=2026,
            gross_salary=march_salary.monthly_gross,
            total_deductions=200.0,
            net_salary=march_salary.monthly_gross - 200.0,
            generated_by=1,
            basic=basic_march,
            hra=hra_march,
            special_allowance=round(march_salary.special_allowance_annual / 12, 2),
            conveyance=round(march_salary.conveyance_annual / 12, 2),
            medical_allowance=round(march_salary.medical_allowance_annual / 12, 2),
            other_allowance=round(march_salary.other_allowance_annual / 12, 2),
            professional_tax=200.0,
            pf=0.0,
            variable_pay=0.0,
            salary_history_id=march_salary.id if isinstance(march_salary, EmployeeSalaryHistory) else None,
        )
        saved = get_salary_slip_history(db, user.user_id, month=3, year=2026)
        assert saved is not None
        assert abs(saved.basic - basic_march) < 0.01
        assert abs(saved.hra - hra_march) < 0.01
        print(f"✅ PASSED: Salary slip history saved with full frozen components: Basic={saved.basic}, HRA={saved.hra}, Gross={saved.gross_salary}, Net={saved.net_salary}")

        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")
        return True
    finally:
        # Clean up test user records
        try:
            db.query(SalarySlipHistory).filter(SalarySlipHistory.user_id == user.user_id).delete()
            db.query(SalaryIncrement).filter(SalaryIncrement.user_id == user.user_id).delete()
            db.query(EmployeeSalaryHistory).filter(EmployeeSalaryHistory.user_id == user.user_id).delete()
            db.query(EmployeeSalary).filter(EmployeeSalary.user_id == user.user_id).delete()
            db.query(User).filter(User.user_id == user.user_id).delete()
            db.commit()
        except Exception:
            db.rollback()
        db.close()

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
