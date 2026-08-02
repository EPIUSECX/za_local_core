# Statutory source governance

Every statutory value must be effective-dated and traceable to a submitted **Approved** source and rate pack.
Record the authority, exact title/version, publication and effective dates, official URL, privately stored source
file, SHA-256 checksum, independent reviewer and impacted capabilities. A catalog entry is only a preparation aid:
it is not approved merely because the app seeded it.

The packaged 2026/27 catalog contains these official references:

- [SARS Guide for Employers in respect of Employees' Tax (2027)](https://www.sars.gov.za/guide-for-employers-in-respect-of-employees-tax-2027/).
- [SARS PAYE Employer Reconciliation BRS version 25.3.0](https://www.sars.gov.za/wp-content/uploads/Docs/PAYE/BRS/SARS_PAYE_BRS-PAYE-Employer-Reconciliation_V25-3-0.pdf), applicable from 1 March 2026 until replaced.
- [Government Gazette 54577, General Notice 3910](https://www.gov.za/sites/default/files/gcis_document/202604/54577gen3910.pdf): COIDA maximum annual earnings of R668,000 per employee from 1 March 2026.
- [Department of Employment and Labour BCEA earnings-threshold notice](https://www.labour.gov.za/Media-Desk/Media-Statements/Pages/Department-of-Employment-and-Labour-sets-a-new-threshold-in-the-protection-of-employees-.aspx): R269,900.90 per year from 1 May 2026.
- [Government Gazette 54075, Notice 7083](https://www.gov.za/sites/default/files/gcis_document/202602/54075rg11941gon7083.pdf): general National Minimum Wage of R30.23 per ordinary hour from 1 March 2026.

These references do not by themselves prove automated coverage. In particular, a BRS entry does not mean an
export has passed SARS import validation, and an NMW entry does not cover every sectoral or worker-category rule.
Keep unsupported outputs as **Controlled Manual** or **Preview** until their owning app has independently reviewed
golden tests and external acceptance evidence.

Resolve historical documents by their payroll or transaction date—not the current date. Missing or overlapping
approved configuration must block calculation. Annual and mid-year changes require a change review, regression
tests on both sides of the effective date, and practitioner approval.

The linked authority pages and guides are evidence inputs, not legal opinions. Archive the exact retrieved file;
do not treat a changing landing page or a seeded catalog URL as the reviewed source version.
