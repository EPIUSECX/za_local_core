# South Africa VAT Settings

Create one company-scoped settings record for each South African VAT vendor. Confirm the 10-digit VAT registration number, SARS-allocated filing category and every output/input VAT account.

## Approved statutory controls

The standard rate and all registration and tax-invoice thresholds are read-only. Select an explicit **Statutory Control Date** and save. The app resolves all five controls from one submitted `ZA Statutory Rate Pack` and one submitted private `ZA Statutory Source`; it does not fall back to today's date or a hard-coded value:

- `vat.standard_rate` (`Percentage`)
- `vat.registration.compulsory_threshold` (`Amount`)
- `vat.registration.voluntary_threshold` (`Amount`)
- `vat.invoice.no_invoice_max` (`Amount`)
- `vat.invoice.full_invoice_threshold` (`Amount`)

For dates from 1 April 2026, the reviewed pack should contain 15%, R2,300,000, R120,000, R50 and R5,000
respectively. Earlier documents require the approved historical pack; never extend these thresholds backwards.
Attach and checksum the retrieved SARS evidence before approving it. Official references:

- [SARS Budget 2026 VAT threshold FAQ](https://www.sars.gov.za/about/sars-tax-and-customs-system/budget/budget-2026-frequently-asked-questions/)
- [SARS tax-invoice requirements](https://www.sars.gov.za/businesses-and-employers/government/tax-invoices/)
- [SARS other tax rates](https://www.sars.gov.za/tax-rates/other-taxes/)

Do not extend an effective-to date automatically. A reviewer must approve the source and rate pack for every later period or changed value.

Before using **Apply Recommended VAT Setup**, select the Company, Statutory Control Date, VAT Vendor Type,
SARS Filing Category, Filing Day, and the company's Output and Input VAT control accounts. The standard VAT rate
is deliberately not entered by the user and is not a client-side save prerequisite: the server resolves it from the
approved date-effective rate pack while saving. The action then creates or updates the recommended tax templates and
tracked accounts. Zero-rated and exempt rows always remain at 0%; if an older record shows another percentage, save
the settings to normalise it.

Posting accounts must be enabled, non-group Tax accounts belonging to the same company. Only a System Manager can
run the bootstrap action. It creates or rebuilds the app's named recommended Sales/Purchase/Item Tax Templates and
applies their tax rows from the selected accounts and approved rate. Back up and review templates first; do not use
bootstrap where a practitioner has intentionally customised a template with one of those generated titles.

The app prepares VAT working papers. SARS eFiling submission and acceptance remain external controlled steps, with the private receipt retained through the core filing evidence model.

Accounts Managers maintain settings; Accounts Users have read-only access. Company/User Permissions still apply.
Approval of the source/rate pack and approval of a VAT201 filing are separate accountable actions.
