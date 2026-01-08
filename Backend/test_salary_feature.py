"""
Test script for Salary Slip and Increment Letter feature
Run this to verify the PDF generation works correctly
"""
import sys
import os

# Add the Backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from app.services.salary_pdf_services import (
    generate_salary_slip_pdf,
    generate_salary_annexure_pdf,
    generate_increment_letter_pdf,
    generate_offer_letter_pdf
)


def test_salary_slip():
    """Test salary slip PDF generation"""
    print("\n📄 Testing Salary Slip PDF generation...")
    
    try:
        pdf_buffer = generate_salary_slip_pdf(
            employee_name="Avadhut Balasaheb Shinde",
            employee_id="SIT1256",
            designation="Backend developer",
            location="Pune",
            doj="21-07-2023",
            pan="OVWPS3792G",
            uan="NA",
            month=9,
            year=2025,
            working_days=22,
            pf="NA",
            variable_pay=0.0,
            basic=14583.50,
            hra=7291.75,
            special_allowance=4691.75,
            medical_allowance=1100.00,
            conveyance=1250.00,
            other_allowance=250.00,
            professional_tax=200.00,
            other_deduction=700.00,
            payment_mode="Bank Transfer"
        )
        
        # Save to file for verification
        output_path = "static/test_salary_slip.pdf"
        os.makedirs("static", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_buffer.getvalue())
        
        print(f"✅ Salary slip PDF generated successfully: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating salary slip: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_salary_annexure():
    """Test salary annexure PDF generation"""
    print("\n📄 Testing Salary Annexure PDF generation...")
    
    try:
        pdf_buffer = generate_salary_annexure_pdf(
            employee_name="Avadhut Balasaheb Shinde",
            designation="Backend developer",
            location="Pune",
            basic_annual=175002,
            hra_annual=87501,
            special_allowance_annual=56301,
            conveyance_annual=15000,
            medical_allowance_annual=13200,
            other_allowance_annual=3000,
            professional_tax_annual=2500,
            other_deduction_annual=8300
        )
        
        # Save to file for verification
        output_path = "static/test_salary_annexure.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_buffer.getvalue())
        
        print(f"✅ Salary annexure PDF generated successfully: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating salary annexure: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_increment_letter():
    """Test increment letter PDF generation"""
    print("\n📄 Testing Increment Letter PDF generation...")
    
    try:
        pdf_buffer = generate_increment_letter_pdf(
            employee_name="Avadhut Balasaheb Shinde",
            designation="Backend developer",
            location="Pune",
            previous_salary=23334.00,
            increment_amount=5833.00,
            new_salary=29167.00,
            effective_date=datetime(2025, 2, 3),
            letter_date=datetime(2025, 1, 22)
        )
        
        # Save to file for verification
        output_path = "static/test_increment_letter.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_buffer.getvalue())
        
        print(f"✅ Increment letter PDF generated successfully: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating increment letter: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_offer_letter():
    """Test offer letter PDF generation"""
    print("\n📄 Testing Offer Letter PDF generation...")
    
    try:
        pdf_buffer = generate_offer_letter_pdf(
            employee_name="Avadhut Balasaheb Shinde",
            designation="Backend developer",
            location="Pune",
            joining_date=datetime(2023, 7, 21),
            basic_annual=175002,
            hra_annual=87501,
            special_allowance_annual=56301,
            conveyance_annual=15000,
            medical_allowance_annual=13200,
            other_allowance_annual=3000,
            professional_tax_annual=2500,
            other_deduction_annual=8300
        )
        
        # Save to file for verification
        output_path = "static/test_offer_letter.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_buffer.getvalue())
        
        print(f"✅ Offer letter PDF generated successfully: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating offer letter: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Salary Slip & Increment Letter Feature Test")
    print("=" * 60)
    
    results = []
    
    results.append(("Salary Slip", test_salary_slip()))
    results.append(("Salary Annexure", test_salary_annexure()))
    results.append(("Increment Letter", test_increment_letter()))
    results.append(("Offer Letter", test_offer_letter()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! PDF files saved in static/ folder.")
    else:
        print("⚠️ Some tests failed. Check the errors above.")
    print("=" * 60)
