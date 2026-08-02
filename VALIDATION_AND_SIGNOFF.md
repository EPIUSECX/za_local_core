# Validation and sign-off status

Updated: 2 August 2026

## Release candidate

The technical release candidate is the four-app `1.0.0` suite, installed in this order:

1. `za_local_core`
2. `za_local_finance`
3. `za_local_payroll`
4. `za_local_workplace`

The validated site is `za-local-production-e2e.test`. It contains Frappe, ERPNext and HRMS v16 plus the four
apps above; the legacy monolithic `za_local` app is not installed. Port 8004 was used for isolated browser and
PDF validation. Port 8000 belongs to the retained legacy environment and is not release evidence.

## Reproducible technical evidence

- 296 application tests passed: core 38, finance 70, payroll 141 and workplace 47.
- Ruff lint and format checks passed for all four apps; 184 JSON files parsed and `git diff --check` passed.
- Two consecutive migrations produced the same core-state fingerprint:
  `a549b5e14073acc3bfb2149b091249d6efe9f83f6b1342c3bea1649af93f91cb`.
- Critical runtime hook ownership is unique; the packaged 651-artifact legacy ownership manifest validates.
- The 2026/27 golden-control invariants passed on 15 salary slips on both the source and restored sites.
- E2E coverage includes monthly and timesheet payroll, recurring and overwrite Additional Salary, PAYE, UIF,
  SDL, ETI, retirement and medical treatment, employer contributions, EMP201, IRP5/IT3(a), EMP501, FNB EFT,
  VAT201 review/approval/filing evidence, COIDA Return of Earnings, Workplace Injury and OID Claim lifecycles.
- The Salary Structure browser check confirms that only `max_benefits` is hidden; the timesheet flag, Salary
  Component and Hour Rate remain visible in their shared section.
- SA Overview, VAT, Payroll, Labour and COIDA workspaces load under one SA Localisation shell. VAT201 loads
  without the legacy “Module SA VAT not found” error.
- Salary Slip, IRP5, Sales Invoice, VAT201 and COIDA PDFs rendered and were visually checked for clipping,
  unsafe debug text and address layout.
- A full database/public/private/config backup restored to `za-local-production-restore.test`; source and restore
  evidence JSON, 11 file hashes, migration fingerprint, permissions and statutory invariants match.
- Guest access is denied for Sales Invoice readiness, EMP501 export and workplace injury health data.
- The federated practitioner and end-user guide registry resolves every installed app contribution with unique
  routes. Frappe Wiki is optional and is not installed on the validated site; packaged Markdown is authoritative
  there, and the publisher exits safely without creating partial pages.

## Current official-source checks

The governed 2026/27 values were checked against the current SARS employer guide and official gazettes,
including PAYE brackets/rebates/medical credits, the R4.95 reimbursive travel rate, the R430,000 retirement cap,
the 15% VAT rate and 2026 VAT-registration thresholds, and the R668,000 COIDA ceiling with R1,621/R560 minimum
assessments. Approved, effective-dated source and rate-pack records remain mandatory at runtime.

## Human and external acceptance gates

The software is technically release-ready, but it cannot certify an employer's configuration or replace statutory
professional judgement. Before live cutover, retain evidence of:

- independent payroll-practitioner approval of mappings, golden calculations and two parallel payroll cycles;
- VAT-practitioner approval of company/account/item treatment and two reconciled VAT periods;
- labour, Employment Equity, skills, COIDA and Information Officer/privacy review of the configured processes;
- FNB acceptance of the generated payment file for the customer's exact banking profile;
- SARS/DEL/Compensation Fund acceptance of any electronic import format claimed by the operator;
- signed cutover, rollback, backup-retention and legacy-retirement decisions.

External SARS, DEL, Compensation Fund and bank submission remains **Controlled Manual** unless a separately
approved integration is configured. A prepared filing, PDF, CSV or XML is not evidence of regulator acceptance;
capture the external receipt in the filing controls.

## Confidence and legacy retirement

Confidence in the tested application code and deterministic E2E controls is high. Confidence for a specific live
employer is conditional on the human gates above and the employer's master data. Keep a final encrypted legacy
backup and rollback procedure until those gates pass. The old `za_local` repository may then be archived; do not
run it beside the extracted apps on the same active site because duplicate modules/controllers create ambiguous
ownership.
