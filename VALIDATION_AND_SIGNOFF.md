# Validation and sign-off status

Updated: 2 August 2026

## Technical evidence completed

- Full legacy compatibility suite: 243 tests passed.
- Dedicated-app suites: core 18, finance 41, payroll 120 and workplace 26 tests passed (205 total).
- Ruff passes across all four repositories.
- Every legacy source artifact has one declared owner; no `migration_split` entries remain.
- Runtime hook audit confirms one owner for payroll, finance, workplace and shared scheduled hooks.
- Fresh site installed with only Frappe, ERPNext, HRMS and the four target apps; no legacy import dependency.
- Two consecutive migrations passed on compatibility and legacy-free sites without changing control totals.
- Legacy-free E2E: 15 submitted Salary Slips, monthly plus timesheet payroll, recurring and bonus pay, EMP201 x6, IRP5/IT3(a), submitted EMP501, FNB payment batch/private CSV, sales and purchase VAT, submitted VAT201, COIDA annual return, injury, medical report and Paid OID claim.
- Fresh-site payroll controls: gross R281,500.00; deductions R38,809.03; net R242,690.97; ETI generated R7,875.00.
- Fresh-site EMP201 controls through August: net PAYE R23,676.09; UIF R1,422.72; SDL R2,250.00; ETI utilised R6,750.00.
- VAT201 controls: output R150.00; input R60.00; payable R90.00.
- A full database, public-file and private-file backup from the legacy-free candidate was restored over an isolated sign-off site. Public and private file hashes matched after pre-existing target-only files were quarantined, and all monetary/document controls matched before and after a second migration.
- The restored site is Desk-ready and browser-smoke-tested: the localisation workspaces load, and the Salary Structure timesheet flag, salary component and hourly rate remain visible while only `max_benefits` is hidden.
- The target-only Desk navigation was browser-tested as one unified application: one **SA Localisation** desktop tile opens the five-icon launcher (SA Overview, SA Payroll, SA VAT, SA Labour and SA COIDA); each workspace retains the SA Localisation identity; and the workspace submenu switches between installed localisation areas without exposing separate app tiles.
- Representative Salary Slip, IRP5, Sales Invoice, VAT201 and COIDA PDFs rendered successfully and were visually inspected. The inspection identified and fixed blank statutory-component defaults that had made the salary-slip PAYE summary disagree with its deduction table.
- Live permission smoke checks on the restored site confirmed Guest access is denied for Sales Invoice tax readiness, EMP501 export and Workplace Injury health data.
- Federated practitioner/end-user guide validates installed contributors, unique routes, content existence and relative links.
- The optional Wiki publisher exits safely when Frappe Wiki is not installed; repository guides remain the authoritative packaged documentation in that deployment shape.
- 2026/27 headline values were rechecked against the SARS 2027 Employer Guide, SARS 2026 Budget Tax Guide and COIDA General Notice 3910 of 2026.

## Release gates still requiring evidence

- Obtain independent payroll-practitioner approval of golden calculations, SARS mappings and 2026/27 sources.
- Obtain VAT-practitioner approval of company treatment/mapping and sample tax documents.
- Obtain labour/EE/skills/COIDA and Information Officer/privacy approval of controlled-manual processes.
- Obtain an FNB acceptance test for the exact customer Online Banking Enterprise profile before live payment.
- Run at least two parallel production-like payroll cycles and two VAT periods with employee/document-level reconciliation.
- Approve cutover, rollback boundary, release versions and the compatibility-app retirement date.

## Confidence

Technical extraction and deterministic test confidence is high. Production statutory confidence is deliberately conditional: the software and isolated workflows are strong, but no responsible sign-off should call the suite universally compliant until the external practitioner, bank, company-configuration, parallel-run and restore gates above are signed.
