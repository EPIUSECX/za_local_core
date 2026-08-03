<div align="center">

<img src="za_local_core/public/images/za_local_core_logo.svg" height="128" alt="SA Localisation Core logo">

# SA Localisation Core

**The governance foundation for South African localisation on Frappe and ERPNext**

[![CI](https://github.com/EPIUSECX/za_local_core/actions/workflows/ci.yml/badge.svg)](https://github.com/EPIUSECX/za_local_core/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](license.txt)
[![Frappe v16](https://img.shields.io/badge/frappe-v16-0089ff.svg)](https://frappeframework.com)

</div>

## What this app is

SA Localisation Core is the shared foundation of the South African localisation
suite. It does not calculate tax. It answers the questions every South African
compliance feature depends on:

- Which statutory rule applies to this company, on this date, and who approved it?
- Is this capability ready for production use, or does it still need a human?
- Which obligation is due, who prepared the filing, and what did the authority
  send back?
- Where is the evidence, and can it be altered after approval?

It also owns the shared Desk experience, so the suite presents itself as one
**SA Localisation** application rather than four separate apps.

## Why it exists

South African statutory values change every year, and several of them change
mid-year. A payroll or VAT engine that hard-codes a rate is wrong the moment the
gazette moves — and worse, it is wrong silently.

This app makes the provenance of every statutory value explicit and
date-effective. A rate is usable only when it is attached to a recorded source,
carries effective dates, and has been approved by someone other than its author.
Rules are never guessed, and never resolved against today's date when the
transaction date is known.

## Key features

- **Company Compliance Profile** — records which obligations actually apply to a
  company, so a business that is not a designated employer or not a VAT vendor is
  never asked for returns it does not owe.
- **Statutory Sources** — immutable records of the gazette, guide or BRS a rule
  came from, with publication date, URL and evidence checksum.
- **Statutory Rate Packs** — effective-dated, reviewer-approved values with
  overlap rejection, so two packs can never both claim the same date.
- **Compliance Obligations and Calendar** — what is due, for which period, by when.
- **Filings and Submission Receipts** — separation of preparer and approver, plus
  a place to capture the authority's actual acknowledgement.
- **Feature Readiness** — every capability in the suite declares whether it is
  Production, Controlled Manual, Preview, Unsupported or Blocked, with the reason
  and the remediation route.
- **POPIA and PAIA registers** — Information Officer registrations, processing
  activities, retention schedules, operator agreements, cross-border transfers,
  data-subject requests, personal-information incidents and PAIA manuals.
- **Shared Desk shell** — one SA Localisation app tile and workspace switcher
  across every installed domain.

## Country scope

Every statutory rule in this suite is gated on the company's country. A site may
hold companies in several countries; those outside South Africa keep stock
Frappe, ERPNext and HRMS behaviour and are never blocked by South African setup
they cannot complete.

`za_local_core.localisation.is_south_african_company` is the single owner of that
decision. A blank or unknown company is treated as out of scope, so an incomplete
document is reported by its own DocType rather than by a localisation error.

## Capability status

| Capability | Status | What that means |
| --- | --- | --- |
| Statutory source, rate and filing governance | Controlled Manual | A designated reviewer approves source evidence, effective dates and each production feature |
| POPIA and PAIA registers | Controlled Manual | The app records controls and evidence; regulator submissions, legal interpretation and incident-notification decisions remain accountable-person duties |

Read the live values in the Desk under **SA Overview → Feature Readiness**. No
capability in this suite ships as Production until an authorised reviewer sets it.

## Under the hood

- [Frappe Framework](https://frappeframework.com) — the DocType model,
  permissions, background jobs and Desk UI this app is built on.
- [ERPNext](https://erpnext.com) — supplies the Company model the compliance
  profile hangs off.
- **No HRMS dependency.** A site that never runs payroll can install this app and
  `za_local_finance` alone.

## The suite

```
ERPNext
└── za_local_core            governance, sources, rate packs, filings, POPIA/PAIA
    ├── za_local_finance     VAT, tax invoices, VAT201
    └── za_local_payroll     PAYE, UIF, SDL, ETI, EMP201/501, IRP5   (+ HRMS)
        └── za_local_workplace   BCEA, Employment Equity, skills, COIDA   (+ HRMS)
```

Install in that order. Each app declares its `required_apps`, so bench enforces
it as well.

## Production setup

```bash
bench get-app za_local_core https://github.com/EPIUSECX/za_local_core.git --branch main
bench --site <your-site> install-app za_local_core
bench --site <your-site> migrate
```

Then create a **ZA Company Compliance Profile** for each South African company
before configuring any domain app.

Do not run this suite alongside the legacy `za_local` monolith on the same active
site: duplicate modules and controllers create ambiguous ownership. Rehearse a
populated legacy upgrade on an isolated clone and keep a separate rollback bench.

Before a first live period, read [VALIDATION_AND_SIGNOFF.md](VALIDATION_AND_SIGNOFF.md)
for the evidence this release carries and the human gates it does not replace, and
[CUTOVER_RUNBOOK.md](CUTOVER_RUNBOOK.md) for the controlled cutover and rollback
procedure.

## Development setup

```bash
bench get-app za_local_core /path/to/za_local_core
bench --site <dev-site> install-app za_local_core
bench --site <dev-site> set-config allow_tests true
bench --site <dev-site> run-tests --app za_local_core
```

Static checks from the bench root:

```bash
uvx ruff check apps/za_local_core
uvx ruff format --check apps/za_local_core
```

Tests create and submit documents. Run them on a disposable site or an approved
restored copy, never on a production site.

## Documentation

| Document | Purpose |
| --- | --- |
| [VALIDATION_AND_SIGNOFF.md](VALIDATION_AND_SIGNOFF.md) | Release evidence, country scope, uninstall contract, outstanding human gates |
| [CUTOVER_RUNBOOK.md](CUTOVER_RUNBOOK.md) | Cutover, rehearsal and rollback procedure |
| [MIGRATION_PLAN.md](MIGRATION_PLAN.md) | What this app owns and how it was extracted |
| [MULTI_APP_MIGRATION_PROGRAMME.md](MULTI_APP_MIGRATION_PROGRAMME.md) | Cross-repository migration waves |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [SECURITY.md](SECURITY.md) | Reporting a vulnerability |
| [SUPPORT.md](SUPPORT.md) | Getting help |

Practitioner and end-user guides ship as Markdown under
`za_local_core/practitioner_guide/content/`. When Frappe Wiki is installed, a
System Manager can publish the federated guide from every installed localisation
app:

```bash
bench --site <site> execute za_local_core.practitioner_guide.stage.stage_space
```

This publishes `/sa-guide` and `/sa-user-guide`. Where Wiki is absent, the
packaged Markdown is authoritative.

## Filing boundary

This suite prepares statutory working papers. It does **not** submit them.

SARS, the Department of Employment and Labour, the Compensation Fund, SETAs and
CIPC submissions are **Controlled Manual** unless a separately approved
integration is configured. Record the authority's acknowledgement as a Submission
Receipt; a generated PDF, CSV or XML is not evidence that a return was accepted.

Installing this app does not make an employer or vendor compliant, and nothing
here is a legal certification.

## Uninstalling

`bench uninstall-app` removes this suite's DocTypes and every schema
customisation it owns: Custom Fields, Property Setters, Print Formats and
Workspaces all carry an owning module, and this app additionally removes the
`ZA Compliance` roles, which Frappe cannot reclaim by module.

Business and audit records are deliberately retained. Salary Components, Payroll
Periods, Income Tax Slabs, approved statutory sources, rate packs, filings and
submission receipts are a company's payroll and compliance history, not app
schema. Remove them only through a reviewed data decision.

## Contributing

Install the repository's pre-commit hooks before changing code:

```bash
cd apps/za_local_core
pre-commit install
```

Ruff, ESLint, Prettier and pyupgrade run on commit. A change to a statutory value
must arrive with its source record, its effective dates and a test.

## License

MIT — see [license.txt](license.txt).
