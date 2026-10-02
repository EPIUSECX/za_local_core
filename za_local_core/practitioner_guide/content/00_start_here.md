# Start here: first-run setup

An ordered path from an installed site to a working South African configuration. Every step names where it lives in
the Desk, because knowing which DocType to open is not the same as knowing where to find it. Work top to bottom:
each step assumes the ones above it are done.

The Desk also carries this as a checklist, under **Getting Started** in each workspace's sidebar: *South African
Localisation Setup* on **SA Overview**, and one each on **SA VAT** (Accounts Manager), **SA Payroll** (Payroll
Manager), **SA Labour** and **SA COIDA** (HR Manager). The checklists appear only once the setup wizard has been
completed in the browser. A "Create" step ticks itself once its record exists; a "Review" or "Confirm" step ticks
when you open it. Those checklists and this page cover the same ground, so use whichever you prefer.

## Before you start: who does what

One thing decided here saves rework later. Approving a statutory source or rate pack is blocked for the user who
created the record, and a company compliance profile needs three people: one to create it, a second to review it
and a third to approve it. The records this app prepares are owned by the account that installed it.

**Create named users and approve as them.** Give at least one **ZA Compliance Reviewer** and one **ZA Compliance
Manager**. That is what an auditor expects to see, and it is the only way the approval evidences anything.

A **System Manager** may approve regardless, so a single-administrator site is never deadlocked. It is not a free
pass: every time the rule is bypassed, a comment naming the user and what was skipped is written on the document,
and an auditor reading that record will see it. Use it to get a site moving, not as the standing arrangement.

Roles are at `/desk/user`. User is a Frappe master, so no South African workspace links it.

## 1. Complete the ERPNext setup wizard

Country **South Africa** and currency **ZAR**. This creates the chart of accounts, fiscal year, genders and warehouse
types that everything downstream expects, and it is the point at which the real currency is known.

Only after the wizard do the workspace metrics carry the right currency symbol. If you installed the apps before
running the wizard and see foreign symbols on the number cards, run `bench --site <site> migrate` once.

## 2. Confirm the company

*SA VAT → Organisation → Company*, or `/desk/company`.

Confirm the 10-digit VAT registration number, the PAYE and SDL reference numbers and the default currency.
Everything downstream is company-scoped, so a wrong abbreviation or currency here is expensive to unwind. Detail:
[Company and Registration Details](../foundation-setup-both-tracks/company-registration).

## 3. Approve the statutory sources

*SA Overview → Configuration → Statutory Sources*, or `/desk/za-statutory-source`.

Installing seeds SARS, COIDA, BCEA and NMW catalogue metadata as **drafts**. A draft is a preparation aid and
resolves nothing. For each one you intend to rely on:

1. Follow the recorded URL and retrieve the official document yourself.
2. Attach it in **Retrieved Source File** as a **private** file. Public attachments are rejected.
3. **SHA-256 Checksum** fills itself in from the file when you save, and is read-only. It is the tamper-evidence
   record: replace the attachment later and the stored digest no longer matches, so approval is refused.
4. Set **Reviewed By** to a named reviewer and submit.

If the recorded URL is a web page rather than a document, print it to PDF and attach that. The evidence is
whatever you actually retrieved, and the digest covers exactly those bytes.

## 4. Approve the statutory rate packs

*SA Overview → Configuration → Statutory Rate Packs*, or `/desk/za-statutory-rate-pack`.

Effective-dated values resolve only from approved packs. There is no fallback anywhere in the suite, by design: a
missing or overlapping pack must block a calculation rather than quietly substitute a number.

A VAT pack for 1 April 2026 to 31 March 2027 is prepared for you, holding the standard rate, both registration
thresholds and both tax-invoice thresholds. Check every value against the evidence you approved in step 3, set
**Reviewed By** and submit. The pack cannot be submitted until its source is approved.

Two things worth knowing before you rely on this:

- The prepared values are a transcription aid so nobody hand-enters five rule keys or invents one. They are not a
  legal opinion. The first reviewer to skim a pre-filled form is the failure mode this control exists to catch.
- Nothing covers dates before 1 April 2026, and no historical figures are supplied. Earlier periods need their own
  reviewed pack. Never widen an existing window to reach an earlier date.

Payroll adds its own dependencies here: the BCEA earnings threshold and every national minimum wage category need
an approved **Labour** pack, and COIDA assessable earnings need a **COIDA** pack. Full detail:
[Statutory Source Governance](../reference-operations/statutory-source-governance).

## 5. Record the company compliance profile

*SA Overview → Configuration → Company Compliance Profiles*, or `/desk/za-company-compliance-profile`.

One submitted, enabled profile per South African company, recording which capabilities are approved for production
and which stay controlled manual. Feature Readiness must not claim Production for a submission channel that is
still manual.

Feature Readiness can be lowered freely, but never raised directly. Record the higher status in **Proposed Status**
with private approval evidence and a named approver; that approver, who cannot be the proposer, selects **Approve
Proposed Status**. A new readiness record cannot start at Production.

## 6. Configure VAT

*SA VAT → Configuration → South Africa VAT Settings*, or `/desk/south-africa-vat-settings`.

Set the **Statutory Control Date** inside the window you approved in step 4, then the VAT vendor type, SARS filing
category, filing day, and the company's Output and Input VAT control accounts. Set the **Capital Goods Input VAT Account**
and **Import VAT Account** as well: capital and import input tax post to their own ledgers, and each must be
different from the general input and output accounts.

Do not type a VAT rate. The standard rate, all four thresholds and the VAT Rates table populate themselves from the
approved pack, along with the pack and source checksums that prove where they came from. A rate typed by hand has
no provenance and defeats the control.

If the save is refused, the error names the pack covering that date and the one action that clears it. Then:
[South Africa VAT Settings](../vat-finance/vat-settings) and
[Tax Templates and Classification](../vat-finance/tax-templates).

## 7. Payroll foundations

Skip this section if `za_local_payroll` is not installed.

*SA Payroll → Configuration*. In order:

1. **Payroll settings and prerequisites** — [Payroll Prerequisites and Settings](../full-suite-payroll-foundations/payroll-prerequisites-settings).
2. **Payroll Periods** (`/desk/payroll-period`) — the South African tax year, 1 March to end February.
3. **Income Tax Slabs** (`/desk/income-tax-slab`) — one submitted slab per tax year and company. PAYE is annualised
   against these, so a missing year blocks the run for that period.
4. **Statutory rate data** — rebates, the medical scheme fees tax credit, UIF ceiling and SDL rate:
   [Statutory Rate Data](../full-suite-payroll-foundations/statutory-rate-data).
5. **Salary Components** (`/desk/salary-component`) — check each component's PAYE inclusion percentage and its UIF,
   SDL and COIDA applicability flags. These decide the statutory bases, so a wrong flag misstates EMP201 rather
   than only a payslip: [Salary Components](../full-suite-payroll-foundations/salary-components).
6. **Salary Structures** (`/desk/salary-structure`) — [Salary Structures](../full-suite-payroll-foundations/salary-structures).
7. **Employees** — [Employee Master](../full-suite-employees/employee-master).

Then run payroll: [Payroll Entry and Salary Slips](../full-suite-running-payroll/payroll-entry-salary-slips).

## 8. Labour, skills and COIDA

Also payroll-only. Record the SETA, any bargaining council and any sectoral determination before relying on
minimum-wage or leave validation, and set the COIDA industry class and assessment rate:
[SA Labour and Skills](../sa-labour-coida/sa-labour) and
[COIDA, Injuries and Claims](../sa-labour-coida/sa-coida).

## 9. Verify before you rely on it

Work through [Post-Install Verification](post-install-verification). It is a checklist of the end state, not of the
steps above, so it catches what a step half-finished. In particular confirm that no approved source or pack is
still carrying placeholder evidence, and that preparation, review and approval sit with different people wherever
the workflow requires it.

## 10. Publish these guides on the site

*SA Overview → Documentation → Publish Localisation Guides*, or `/desk/sa-localisation-guides`.

With Frappe Wiki installed, this publishes the practitioner and end-user guides onto this site so the team reads
them in the Desk. The same content ships as Markdown in each app repository either way, and stays authoritative.

## What this does not do for you

The suite prepares working papers and refuses to guess. SARS eFiling submission and acceptance, Department of
Employment and Labour submissions and COIDA filing remain external controlled steps, with the private receipt
retained through the filing evidence model. A green setup is not a filing, and a green test suite is not
practitioner review of rates, mappings and company-specific configuration.
