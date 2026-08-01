# Validation and sign-off status

Updated: 1 August 2026

## Technical evidence completed

- Full legacy compatibility suite: 243 tests passed.
- Dedicated-app suites: core 15, finance 41, payroll 119 and workplace 26 tests passed.
- Ruff passes across all four repositories.
- Every legacy source artifact has one declared owner; no `migration_split` entries remain.
- Runtime hook audit confirms one owner for payroll, finance, workplace and shared scheduled hooks.
- Fresh site installed with only Frappe, ERPNext, HRMS and the four target apps; no legacy import dependency.
- Two consecutive migrations passed on compatibility and legacy-free sites without changing control totals.
- Legacy-free E2E: 15 submitted Salary Slips, monthly plus timesheet payroll, recurring and bonus pay, EMP201 x6, IRP5/IT3(a), submitted EMP501, FNB payment batch/private CSV, sales and purchase VAT, submitted VAT201, COIDA annual return, injury, medical report and Paid OID claim.
- Fresh-site payroll controls: gross R281,500.00; deductions R38,809.03; net R242,690.97; ETI generated R7,875.00.
- Fresh-site EMP201 controls through August: net PAYE R23,676.09; UIF R1,422.72; SDL R2,250.00; ETI utilised R6,750.00.
- VAT201 controls: output R150.00; input R60.00; payable R90.00.
- Federated practitioner/end-user guide validates installed contributors, unique routes, content existence and relative links.
- 2026/27 headline values were rechecked against the SARS 2027 Employer Guide, SARS 2026 Budget Tax Guide and COIDA General Notice 3910 of 2026.

## Release gates still requiring evidence

- Restore the final candidate backup onto the isolated sign-off site and compare files plus all monetary controls.
- Complete browser smoke tests for role-based workspaces, the Salary Structure hourly/timesheet fields and critical workflows.
- Render and visually inspect representative Salary Slip, IRP5/IT3(a), VAT invoice, VAT201 and COIDA PDFs.
- Run permission-denial tests with representative real roles and User Permissions on the restored candidate.
- Obtain independent payroll-practitioner approval of golden calculations, SARS mappings and 2026/27 sources.
- Obtain VAT-practitioner approval of company treatment/mapping and sample tax documents.
- Obtain labour/EE/skills/COIDA and Information Officer/privacy approval of controlled-manual processes.
- Obtain an FNB acceptance test for the exact customer Online Banking Enterprise profile before live payment.
- Run at least two parallel production-like payroll cycles and two VAT periods with employee/document-level reconciliation.
- Approve cutover, rollback boundary, release versions and the compatibility-app retirement date.

## Confidence

Technical extraction and deterministic test confidence is high. Production statutory confidence is deliberately conditional: the software and isolated workflows are strong, but no responsible sign-off should call the suite universally compliant until the external practitioner, bank, company-configuration, parallel-run and restore gates above are signed.
