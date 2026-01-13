
import unittest
from pydantic import ValidationError
import sys
import os

# Add Backend to sys.path
sys.path.append(os.path.abspath("j:/emss/EMS-Shekru-Web-App/Backend"))

from app.schemas.salary_schema import EmployeeSalaryCTCCreate

class TestSalarySchemaValidation(unittest.TestCase):
    def test_valid_uan_ifsc(self):
        data = {
            "user_id": 1,
            "annual_ctc": 500000,
            "uan_number": "123456789012",
            "ifsc_code": "SBIN0001234"
        }
        model = EmployeeSalaryCTCCreate(**data)
        self.assertEqual(model.uan_number, "123456789012")
        self.assertEqual(model.ifsc_code, "SBIN0001234")

    def test_invalid_uan_short(self):
        data = {
            "user_id": 1,
            "annual_ctc": 500000,
            "uan_number": "12345",  # Too short
            "ifsc_code": "SBIN0001234"
        }
        with self.assertRaises(ValidationError) as cm:
            EmployeeSalaryCTCCreate(**data)
        self.assertIn("UAN must be exactly 12 numeric digits", str(cm.exception))

    def test_invalid_uan_alpha(self):
        data = {
            "user_id": 1,
            "annual_ctc": 500000,
            "uan_number": "12345678901A",  # Contains letter
            "ifsc_code": "SBIN0001234"
        }
        with self.assertRaises(ValidationError) as cm:
            EmployeeSalaryCTCCreate(**data)
        self.assertIn("UAN must be exactly 12 numeric digits", str(cm.exception))

    def test_invalid_ifsc_length(self):
        data = {
            "user_id": 1,
            "annual_ctc": 500000,
            "uan_number": "123456789012",
            "ifsc_code": "SBIN000"  # Too short
        }
        with self.assertRaises(ValidationError) as cm:
            EmployeeSalaryCTCCreate(**data)
        self.assertIn("Bank IFSC must be exactly 11 alphanumeric characters", str(cm.exception))

    def test_valid_optional_empty(self):
        # Test that None is allowed
        data = {
            "user_id": 1,
            "annual_ctc": 500000,
            "uan_number": None,
            "ifsc_code": None
        }
        model = EmployeeSalaryCTCCreate(**data)
        self.assertIsNone(model.uan_number)

if __name__ == '__main__':
    unittest.main()
