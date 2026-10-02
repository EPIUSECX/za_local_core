# Operations and troubleshooting

Before every release: back up the database, public/private files and encryption configuration; verify restore on an
isolated target-only site; run migrations twice; compare fingerprints, file hashes and control totals; build assets;
and run all app suites.

If a statutory calculation cannot resolve an approved rate or company-scoped master, stop the process and repair configuration. Do not enter guessed values to make payroll or a return submit.

External filing and payment evidence must include the authority/bank reference, timestamp, approved amount, attachment and checksum where available. Corrections use amendments or adjustment records; never rewrite submitted history.

Do not load legacy `za_local` and the extracted apps as concurrent runtime writers. Preserve legacy on a separate,
pinned rollback bench until the release-specific populated migration and rollback boundary are approved.

## Compliance calendar

Every ZA Filing creates or links the calendar entry for its company, obligation and period and keeps its status in
step (In Progress, Approved, Filed, Accepted). Cancelling a filing releases the entry (Open, or Overdue after its due
date) until the amended filing links itself. Create entries for periods that have no filing yet, with the due date
from the obligation's rule; a daily task marks open entries past due **Overdue**, and SA Overview counts them.

## Setup checklists

Each SA workspace carries a **Getting Started** checklist shown to the role that owns it: SA Overview (ZA
Compliance Manager), SA VAT (Accounts Manager), SA Payroll (Payroll Manager), SA Labour and SA COIDA (HR Manager);
System Manager sees all. A "Create" step ticks itself once its record exists; "Review" and "Confirm" steps tick when
opened. Migrate refreshes step wording without losing progress.

## Common errors

| Message or symptom | Cause | Action |
|---|---|---|
| VAT Settings will not save; no approved pack | VAT source or rate pack not approved, or control date outside its window | Approve the source, then the pack; set a date inside the window |
| Payroll stops: no approved Payroll rate pack | No Payroll pack covers the date and packaged rates are not allowed | Approve a Payroll pack, or record the decision in **Allow Packaged Statutory Rates** |
| *Create ZA Filing* refused | Obligation not set in Payroll Settings, or due date / filing reviewer / approver missing | Complete them on the submission |
| Filing cannot be approved | Declared amount differs from the ledger | Record a **Difference Explanation** (30+ characters) before review |
| Slip refused: lump sum without directive | No Active Severance / Lump Sum directive covers the slip date | Capture the SARS directive and set it Active |
| Line VAT category refused | Line differs from the item's category without a reason | Record a **VAT Category Reason** |
| "Not permitted" from a checklist step | Role lacks read access (older install) | Run `bench migrate` |

For support, retain the app versions, site version output, relevant document names, Error Log traceback, source version and control totals. Redact personal and banking values.
