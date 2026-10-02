# Statutory source governance

Every statutory value must be effective-dated and traceable to a submitted **Approved** source and rate pack.
Record the authority, exact title/version, publication and effective dates, official URL, privately stored source
file, SHA-256 checksum, independent reviewer and impacted capabilities. A catalog entry is only a preparation aid:
it is not approved merely because the app seeded it.

## Approve the VAT controls before first use

South Africa VAT Settings cannot be saved until one approved rate pack answers all five VAT control keys. There is
no fallback rate, so this is the first task on a new site. Installing the app prepares both records as **drafts**
and nothing more; approving them is a human step, and deliberately so.

1. Open **ZA Statutory Source** `SARS-VAT-CONTROLS-2026-04-01`. Follow the recorded URL, retrieve the official SARS
   document yourself, and attach it in **Retrieved Source File** as a *private* file. Public attachments are
   rejected.
2. **SHA-256 Checksum** is recorded for you from the attached file on save, and cannot be edited. Submitting
   verifies it against the stored bytes again, so an attachment swapped after the fact will fail.
3. Set **Reviewed By** to yourself and submit. Approval needs **ZA Compliance Reviewer** or **ZA Compliance
   Manager**, and the approver may not be the user who created the record. Records the installer prepared are owned
   by the installing account, so approve them as a named user. A System Manager may approve regardless, which
   keeps a single-administrator site moving, but the bypass is recorded as a comment on the document.
4. Open **ZA Statutory Rate Pack** for domain `VAT`, effective 1 April 2026 to 31 March 2027. Check every value
   against the evidence you just attached, set **Reviewed By** and submit. The pack cannot be submitted until its
   source is approved.
5. Return to South Africa VAT Settings. Set a **Statutory Control Date** inside the approved window and save. The
   standard rate, both registration thresholds, both tax-invoice thresholds and the VAT Rates table populate
   themselves, along with the pack and source checksums that prove where they came from.

The seeded values are a transcription aid, not a legal opinion. Verify each one against the retrieved evidence
before you approve; the pack is only trustworthy because a named reviewer checked it.

If a save still fails, the error names the pack covering that date and what is missing. A date outside every
approved window lists the windows that do exist: change the control date, or approve a pack for the period you
actually need. Never widen an existing window to reach an earlier date.

The packaged 2026/27 catalog contains these official references:

- [SARS Guide for Employers in respect of Employees' Tax (2027)](https://www.sars.gov.za/guide-for-employers-in-respect-of-employees-tax-2027/).
- [SARS PAYE Employer Reconciliation BRS version 25.3.0](https://www.sars.gov.za/wp-content/uploads/Docs/PAYE/BRS/SARS_PAYE_BRS-PAYE-Employer-Reconciliation_V25-3-0.pdf), applicable from 1 March 2026 until replaced.
- [Government Gazette 54577, General Notice 3910](https://www.gov.za/sites/default/files/gcis_document/202604/54577gen3910.pdf): COIDA maximum annual earnings of R668,000 per employee from 1 March 2026.
- [Department of Employment and Labour BCEA earnings-threshold notice](https://www.labour.gov.za/Media-Desk/Media-Statements/Pages/Department-of-Employment-and-Labour-sets-a-new-threshold-in-the-protection-of-employees-.aspx): R269,600.90 per year from 1 May 2026 (Government Gazette 54544, GN 7384).
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
