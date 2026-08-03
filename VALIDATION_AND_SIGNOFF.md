# Validation and sign-off status

Updated: 2 August 2026

## Country scope

Every South African statutory rule in this suite is gated on the company's
country. A site may hold companies in several countries: those outside South
Africa keep stock Frappe, ERPNext and HRMS behaviour, including the standard
HRMS bank entry, and are never blocked by South African statutory setup they
cannot complete. `za_local_core.localisation.is_south_african_company` is the
single owner of that decision; a blank or unknown company is treated as out of
scope so the owning DocType reports its own missing mandatory fields.

## Uninstall contract

`bench uninstall-app` removes the suite's DocTypes and every schema
customisation it owns. Custom Fields, Property Setters, Print Formats and
Workspaces all carry an owning module so Frappe reclaims them; `za_local_core`
additionally removes the `ZA Compliance` roles, which have no module field.
Business and audit records — Salary Components, Payroll Periods, Income Tax
Slabs, statutory sources, rate packs, filings and receipts — are retained by
design, because an uninstall must not destroy payroll or compliance history.

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

- 320 application tests passed: core 45, finance 70, payroll 154 and workplace 51. This
  includes country-gating coverage proving a company outside South Africa is unaffected,
  uninstall-hygiene coverage proving every schema customisation declares an owning module, and
  dashboard coverage proving each metric is seeded once, declares its module, is skipped when
  its inputs are absent, and renders on a site with no data.
- All 42 workspace metrics rendered without error on both a zero-data site and the populated
  sign-off site: 26 number cards and 16 charts across the five workspaces.
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

## Legacy suite on a shared bench

The retiring `za_local` suite is only meaningful on a legacy-only site. On a bench that also
holds the extracted apps, both declare the same module names, so `frappe.new_doc` resolves a
DocType to whichever app wins the module map while the legacy unit tests call legacy classes
directly. Eight tests fail from that mismatch alone. This is the duplicate-ownership condition
this programme already declares unsupported, not a defect in either app; run the legacy suite
on a site where only `za_local` is installed.

## Confidence and legacy retirement

Confidence in the tested application code and deterministic E2E controls is high. Confidence for a specific live
employer is conditional on the human gates above and the employer's master data. Keep a final encrypted legacy
backup and rollback procedure until those gates pass. The old `za_local` repository may then be archived; do not
run it beside the extracted apps on the same active site because duplicate modules/controllers create ambiguous
ownership.
