# CTC-Based Payroll System Documentation

## Overview

The new CTC-based payroll system automates salary component calculations based on Annual CTC input. HR only needs to enter the Annual CTC amount, and the system automatically calculates all salary components according to predefined rules.

## Key Features

- **Automatic Calculation**: Enter only Annual CTC, system calculates all components
- **Fixed Components**: Medical, Conveyance, Other allowances are fixed amounts
- **Percentage-based Components**: Basic (50% of CTC), HRA (50% of Basic)
- **Variable Pay Support**: Optional variable pay with percentage or fixed amount
- **Consistent Logic**: Same calculations used for Offer Letters and Salary Slips
- **Validation**: Prevents manual editing of calculated components

## Salary Component Rules

### Fixed Annual Amounts
- **Medical Allowance**: ₹19,200/year (₹1,600/month)
- **Conveyance Allowance**: ₹15,000/year (₹1,250/month)
- **Other Allowance**: ₹3,000/year (₹250/month)
- **Professional Tax**: ₹2,400/year (₹200/month) - Fixed deduction

### Calculated Components
- **Basic Salary**: 50% of Annual CTC
- **HRA**: 50% of Basic Salary
- **Special Allowance**: Remaining amount to reach CTC (CTC - Basic - HRA - Fixed Allowances)

### Variable Pay (Optional)
- **None**: No variable pay
- **Percentage**: Percentage of Annual CTC (0-100%)
- **Fixed Amount**: Fixed annual amount
- **Note**: Variable pay is calculated separately and excluded from monthly in-hand salary

## API Endpoints

### 1. Preview Salary Calculation
```
GET /salary/calculate-preview?annual_ctc=1200000&variable_pay_type=percentage&variable_pay_value=10
```
Preview salary breakdown before saving.

### 2. Get Minimum CTC
```
GET /salary/minimum-ctc
```
Returns minimum CTC required for fixed components.

### 3. Create Salary from CTC
```
POST /salary/employee/from-ctc
```
**Body:**
```json
{
  "user_id": 123,
  "annual_ctc": 1200000,
  "variable_pay_type": "percentage",
  "variable_pay_value": 10,
  "pan_number": "ABCDE1234F",
  "bank_name": "HDFC Bank",
  "bank_account": "12345678901",
  "ifsc_code": "HDFC0001234"
}
```

### 4. Update Salary CTC
```
PUT /salary/employee/{user_id}/update-ctc
```
**Body:**
```json
{
  "annual_ctc": 1500000,
  "variable_pay_type": "fixed",
  "variable_pay_value": 50000
}
```

### 5. Update Non-Calculated Fields
```
PUT /salary/employee/{user_id}
```
**Body:**
```json
{
  "bank_name": "New Bank",
  "bank_account": "98765432109",
  "ifsc_code": "NEWB0001234",
  "variable_pay_type": "none",
  "other_deduction_annual": 5000
}
```

## Calculation Examples

### Example 1: Basic Employee (₹6 LPA)
```
Annual CTC: ₹600,000
├── Basic (50%): ₹300,000
├── HRA (50% of Basic): ₹150,000
├── Medical: ₹19,200
├── Conveyance: ₹15,000
├── Other: ₹3,000
└── Special Allowance: ₹112,800

Monthly In-Hand: ₹49,800 (after ₹200 professional tax)
```

### Example 2: Senior Employee (₹18 LPA + 10% Variable)
```
Annual CTC: ₹1,800,000
├── Basic (50%): ₹900,000
├── HRA (50% of Basic): ₹450,000
├── Medical: ₹19,200
├── Conveyance: ₹15,000
├── Other: ₹3,000
└── Special Allowance: ₹412,800

Variable Pay (10%): ₹180,000 (₹15,000/month - separate)
Monthly In-Hand: ₹149,800 (excluding variable pay)
```

## Database Schema Changes

### New Fields in EmployeeSalary Model
- All existing fields remain unchanged
- Calculations are done in service layer
- Variable pay stored in existing `variable_pay` field

### New Schemas
- `EmployeeSalaryCTCCreate`: For CTC-based creation
- `EmployeeSalaryCTCUpdate`: For CTC updates
- `SalaryCalculationPreview`: For preview responses
- `VariablePayType`: Enum for variable pay options

## Service Layer

### SalaryCalculator Class
Located in `app/services/salary_calculation_service.py`

**Key Methods:**
- `calculate_salary_components()`: Main calculation logic
- `get_minimum_ctc()`: Returns minimum CTC required
- `validate_ctc()`: Validates if CTC is sufficient
- `get_salary_breakdown_summary()`: Human-readable breakdown

### Usage in PDF Generation
The same calculation logic is used in:
- Offer Letter PDF generation
- Salary Slip PDF generation
- Salary Annexure PDF generation

This ensures consistency across all documents.

## Validation Rules

### CTC Validation
- Must be greater than 0
- Must be sufficient to cover fixed components
- Minimum CTC: ₹148,800 (calculated dynamically)

### Variable Pay Validation
- **Percentage**: Must be between 0-100%
- **Fixed Amount**: Must be non-negative
- **Type**: Must be one of: none, percentage, fixed

### Field Restrictions
- **Read-only**: Basic, HRA, Medical, Conveyance, Other, Special Allowance, Professional Tax
- **Editable**: Bank details, Variable Pay settings, Other deductions, PF

## Error Handling

### Common Errors
1. **CTC Too Low**: "CTC amount X is too low. Minimum required CTC: Y"
2. **Invalid Variable Pay**: "Variable pay percentage must be between 0 and 100"
3. **Duplicate Record**: "Salary record already exists for user_id X"

### HTTP Status Codes
- `201`: Created successfully
- `400`: Invalid input/validation error
- `404`: User/record not found
- `409`: Conflict (duplicate record)
- `500`: Server error

## Migration Guide

### For Existing Records
Existing salary records continue to work with the legacy endpoints:
- `POST /salary/employee` (manual entry)
- `PUT /salary/employee/{user_id}` (full update)

### For New Records
Use the new CTC-based endpoints:
- `POST /salary/employee/from-ctc` (automatic calculation)
- `PUT /salary/employee/{user_id}/update-ctc` (CTC update)

## Testing

Run the test suite:
```bash
python Backend/test_payroll_system.py
```

Tests cover:
- Various CTC amounts and variable pay configurations
- Minimum CTC validation
- Variable pay validation
- Error handling
- Salary breakdown summaries

## Benefits

1. **Consistency**: Same calculation logic across all documents
2. **Accuracy**: Eliminates manual calculation errors
3. **Efficiency**: HR only enters CTC, system does the rest
4. **Flexibility**: Supports different variable pay configurations
5. **Validation**: Prevents invalid salary structures
6. **Maintainability**: Centralized calculation logic

## Future Enhancements

Potential future additions:
- PF calculation automation
- Tax calculation integration
- Bonus calculation rules
- Location-based allowance variations
- Grade-wise salary bands