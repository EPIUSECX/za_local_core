# Finance statutory sources and annual review

The runtime configuration must be reviewed against an archived official source
before a company feature is promoted from Preview to Production. Promotion is an
internal release/configuration decision, not legal certification or SARS approval.

Primary current references (reviewed 1 August 2026):

- [SARS Other Taxes](https://www.sars.gov.za/tax-rates/other-taxes/): the standard VAT rate is 15%; from 1 April 2026 the compulsory and voluntary registration thresholds are R2.3 million and R120,000, subject to applicable exceptions.
- [SARS Register for VAT](https://www.sars.gov.za/types-of-tax/value-added-tax/register-for-vat/): registration tests and exceptions must be reviewed for the specific vendor; threshold values alone do not decide registration.
- [SARS Tax Invoices](https://www.sars.gov.za/businesses-and-employers/government/tax-invoices/): full invoice above R5,000, abridged invoice up to R5,000, and no prescribed tax invoice at R50 or less, subject to documentary evidence.
- The VAT Act, official SARS VAT guides and the company's practitioner-approved treatment matrix for zero-rated, exempt, imported, second-hand, blocked-input and adjustment transactions.

For each annual or legislative review:

1. Download the exact official publication and store it as a private File.
2. Record its publication/effective dates, URL and SHA-256 checksum in `ZA Statutory Source`.
3. Have a different authorised reviewer approve the source.
4. Amend effective-dated rules; never rewrite a prior approved period.
5. Re-run invoice-boundary, VAT201, GL-reconciliation, permission and PDF tests.
6. Record practitioner approval in `ZA Feature Readiness` before changing a feature to Production.

The seeded source catalogue is Draft metadata. Store the exact retrieved publication as a private File, not merely
the landing-page URL. Historical transactions before 1 April 2026 require the applicable historical pack.

SARS portal filing and CIPC portal work remain Controlled Manual until an
officially supported interface and acceptance receipt workflow are implemented.
No CIPC or corporate/provisional-tax working-paper workflow is implemented in this repository at this release.
