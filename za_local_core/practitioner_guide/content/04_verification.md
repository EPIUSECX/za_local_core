# Post-install verification

This checks the end state, not the steps that produce it. Work through
[Start Here: First-Run Setup](start-here) first, then confirm:

- all required apps appear in Installed Applications;
- each South African company has exactly one submitted, enabled Approved compliance profile for the date under test;
- current statutory sources and rate packs are approved and effective;
- Payroll Periods and submitted Income Tax Slabs exist per payroll company;
- VAT accounts and templates point to enabled, company-scoped tax ledgers;
- Feature Readiness does not claim Production for unsupported external submission channels;
- `ZA Compliance User`, `ZA Compliance Reviewer` and `ZA Compliance Manager` are assigned to accountable users,
  with distinct people selected for preparation, review and approval where the workflow requires it;
- low-privilege users cannot read payroll, banking, injury or medical records outside their scope;
- two consecutive migrations leave core state and domain monetary controls unchanged;
- the target-only release gate confirms legacy `za_local` is not installed or loaded by the target runtime;

Run server tests for each app and retain the results with the release evidence. Also retain the exact app commits,
backup/file hashes, browser/PDF samples and before/after controls. A green technical suite is necessary but does
not replace practitioner review of rates, mappings and company-specific configuration.
