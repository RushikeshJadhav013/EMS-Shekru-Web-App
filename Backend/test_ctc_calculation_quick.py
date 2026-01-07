"""Quick test for CTC-based salary calculation"""
from app.services.salary_calculation_service import SalaryCalculator

# Test with CTC of 600,000
ctc = 600000
components = SalaryCalculator.calculate_salary_components(ctc)

print('='*60)
print('CTC-BASED SALARY CALCULATION TEST')
print(f'Annual CTC (Input): Rs {ctc:,.2f}')
print('='*60)

print('\nEARNINGS (Annual) - Employee receives this:')
print(f'  Basic:              Rs {components["basic_annual"]:,.2f}')
print(f'  HRA:                Rs {components["hra_annual"]:,.2f}')
print(f'  Special Allowance:  Rs {components["special_allowance_annual"]:,.2f}')
print(f'  Medical:            Rs {components["medical_allowance_annual"]:,.2f}')
print(f'  Conveyance:         Rs {components["conveyance_annual"]:,.2f}')
print(f'  Other:              Rs {components["other_allowance_annual"]:,.2f}')
print(f'  -----------------------------------------')
print(f'  TOTAL GROSS:        Rs {components["total_earnings_annual"]:,.2f}')

print('\nEMPLOYER CONTRIBUTION (added on top of Gross for CTC):')
print(f'  Employer PF (12% of Basic): Rs {components["employer_pf_annual"]:,.2f}')

print('\nCTC CALCULATION:')
print(f'  Total Gross:        Rs {components["total_earnings_annual"]:,.2f}')
print(f'  + Employer PF:      Rs {components["employer_pf_annual"]:,.2f}')
print(f'  + Variable Pay:     Rs {components["variable_pay_annual"]:,.2f}')
print(f'  -----------------------------------------')
print(f'  = CTC:              Rs {components["calculated_ctc"]:,.2f}')

print('\nEMPLOYEE DEDUCTIONS (deducted from Gross):')
print(f'  Professional Tax:   Rs {components["professional_tax_annual"]:,.2f}')
print(f'  Other Tax:          Rs {components["other_tax_annual"]:,.2f}')
print(f'  -----------------------------------------')
print(f'  Total Deductions:   Rs {components["total_employee_deductions_annual"]:,.2f}')

print('\nIN-HAND CALCULATION:')
print(f'  Total Gross:        Rs {components["total_earnings_annual"]:,.2f}')
print(f'  - Deductions:       Rs {components["total_employee_deductions_annual"]:,.2f}')
print(f'  -----------------------------------------')
print(f'  = Net Annual:       Rs {components["net_annual"]:,.2f}')
print(f'  = Monthly In-Hand:  Rs {components["monthly_in_hand"]:,.2f}')

print('\n' + '='*60)
print('VERIFICATION:')
print(f'  Input CTC:          Rs {ctc:,.2f}')
print(f'  Calculated CTC:     Rs {components["calculated_ctc"]:,.2f}')
print(f'  Match: {abs(components["calculated_ctc"] - ctc) < 1}')
print('='*60)
