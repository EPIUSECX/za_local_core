# SA Localisation Core Migration Plan

Status: core ownership, governance contracts and target-only release controls are implemented. Fresh multi-app E2E,
repeated migration and target-only backup/restore evidence are recorded in `VALIDATION_AND_SIGNOFF.md`. A populated
legacy upgrade, release-tag rehearsal, production cutover and external practitioner approval remain release gates.

## Purpose

`za_local_core` owns shared South African compliance infrastructure. It must not contain VAT calculations,
payroll calculations, labour rules, or COIDA transaction logic. Domain apps consume its stable public services.

## Dependency contract

```text
frappe -> erpnext -> za_local_core -> za_local_finance
             |             |
             +-> hrms -----+-> za_local_payroll -> za_local_workplace
```

The core app knows nothing about downstream apps. It publishes services and document events; it does not import
finance, payroll, or workplace modules. The existing `za_local` repository is retained only as a migration source
and rollback artifact. It is not a supported compatibility runtime beside the extracted apps. Target candidates
must run without legacy `za_local`; the four target apps own the active runtime hooks.

## Historical source mapping

The source column records the legacy location; it is not a supported import path. The destination column describes
the implemented target or an intentional replacement.

| Current source in `za_local` | Destination | Treatment |
|---|---|---|
| `za_local/sa_localisation/` | `za_local_core/sa_localisation_core/` | Shared core DocTypes and workspace use the target module identity. |
| `za_local/api/` | `za_local_core/api.py` | App-access and readiness APIs are permission- and method-gated. |
| `za_local/utils/file_utils.py` | `za_local_core/files.py` | Move safe app-resource resolution and traversal protection. |
| `za_local/utils/setup_utils.py` | `za_local_core/install.py` and `migration/` | Replaced by bounded install/backfill/release services; no compatibility import is exposed. |
| `za_local/sa_setup/doctype/za_local_setup/` | Core governance DocTypes and domain settings | The monolithic setup document is not part of the target runtime. |
| `za_local/sa_setup/page/sa_local_help/` | Federated practitioner/end-user guides | The old help page is not retained as a compatibility route. |
| `za_local/sa_setup/workspace/sa_localisation/` | `sa_localisation_core/workspace/sa_overview/` | Core owns the single SA Localisation launcher and overview workspace. |
| `za_local/practitioner_guide/manifest.py` and `stage.py` | `za_local_core/practitioner_guide/` | Core owns provider discovery, validation and optional queued Wiki publication. |
| `za_local/public/js/za_local_feedback.js` | `za_local_core/public/js/` | Retain only shared feedback/error behaviour. |
| Shared shell styles/icons from `za_local/public/` | `za_local_core/public/` | Move brand assets and shared design tokens; domain CSS stays with the domain. |
| Shared portions of `za_local/tasks.py` | `za_local_core/tasks.py` | Core keeps bounded daily compliance-calendar/source checks only. |
| `za_local/sa_setup/statutory_setup.py` | Core/domain install and patch modules | Shared profile/source metadata is core-owned; domain seeds live downstream. |
| Generic Company and Address fields in `sa_setup/custom_fields.py` | Core-owned field manifest | Move only legal identity, trading name, registration number, physical/postal address structure and shared filing-contact fields. |
| Cross-domain setup tests | `za_local_core` and compatibility test harness | Split by owner; retain multi-app installation tests centrally. |

## Content that must not move to core

- Chart of Accounts and VAT settings move to `za_local_finance`.
- Employee, Payroll Settings, Salary Component and Salary Slip fields move to `za_local_payroll`.
- Leave Type, Employee Separation, EE, SETA, bargaining-council and COIDA fields move to `za_local_workplace`.
- Domain print formats, reports, workspaces and schedulers move with their domain.
- Core must not conditionally import HRMS or create HRMS fields.

## New core data model

| DocType | Purpose | Lifecycle |
|---|---|---|
| `ZA Company Compliance Profile` | Determines which registrations, returns and industry rules apply to a Company. | Versioned, company-scoped, approved before activation. |
| `ZA Statutory Source` | Records authority, legislation/guide/BRS, version, URL, publication date and checksum. | Immutable after approval; superseded, never overwritten. |
| `ZA Statutory Rate Pack` | Effective-dated container for approved statutory values. | Submittable and immutable; overlap validation. |
| `ZA Statutory Rate Item` | Typed rate/threshold/formula metadata owned by a domain. | Child table with unit, precision and provenance. |
| `ZA Compliance Obligation` | Applicability rule, frequency, due-date rule, owner and authority. | Versioned rule definition. |
| `ZA Filing` | Company/period instance of an obligation and its internal working paper. | Draft, Reviewed and Approved are internal; receipt evidence derives Filed, Accepted or Rejected; cancellation/amendment preserves history. |
| `ZA Submission Receipt` | External reference, timestamp, declared amount, attachment and checksum. | Immutable evidence record. |
| `ZA Feature Readiness` | States whether a feature is Production, Controlled Manual, Preview or Unsupported. | Conservatively seeded per company and governed by accountable review; a label is not legal certification. |
| `ZA Compliance Calendar Entry` | Materialised filing/payment deadline and escalation state. | Generated idempotently from obligations. |
| `ZA Statutory Change Review` | Impact assessment for a new gazette, guide or BRS. | Requires domain practitioner and technical approval. |

Use Links to Company, User, File, Fiscal Year and other existing ERPNext records. Do not duplicate ERPNext master
data. Add database uniqueness for company/obligation/period and statutory-source version/checksum.

## Compliance additions

### Statutory source governance

- Every rate, threshold, code table and format must reference an approved `ZA Statutory Source`.
- Resolve rules by transaction date, never by `today()` for historical documents.
- Fail payroll/filing loudly when no applicable approved rule exists.
- Prevent overlapping active packs and edits to used/submitted packs.
- Store source checksum and reviewer identity.
- Add annual budget, mid-year legislative-change and BRS-update workflows.

### Filing and evidence controls

- Separate internal submission from external filing.
- Require maker/checker approval for statutory filings and bank files.
- Attach portal receipt or validated import result before marking Filed.
- Record declared, paid and ledger amounts independently and reconcile them.
- Support corrections and amendments without changing historical evidence.
- Make generic exports visibly non-authoritative.

### POPIA and PAIA administration

Add an optional core compliance module for Information Officer registration, processing-activity records, lawful
basis, consent/objection records, data-subject requests, retention schedules, operator agreements, impact
assessments, security incidents, breach notifications, cross-border transfers and PAIA manuals. Frappe permissions
remain the technical access-control layer; this module records organisational controls.

### Observability and operations

- Structured site logger per app with preserved tracebacks.
- Persistent setup-health dashboard with severity and remediation links.
- Idempotent long-queue compliance reminders with delivery audit.
- Feature-level telemetry without personal or payroll values.
- Backup/restore and migration control-total records.

## Setup and migration design

1. Create a source-ownership manifest for every DocType, Custom Field, Property Setter, report, print format and hook.
2. Rehearse on a disposable restored copy and move to a target-only runtime before enabling extracted hooks. Do not
   run legacy and extracted implementations as concurrent writers.
3. Create core DocTypes and backfill compliance profiles from existing Company fields.
4. Import statutory JSON packs as immutable records while preserving their original checksums.
5. Publish shared setup/navigation and federated guides from core; no legacy compatibility API is promised.
6. Transfer field ownership without deleting/recreating Custom Field rows.
7. Replace `after_migrate` data mutation with ordered, idempotent patches.
8. Treat old Python paths as unsupported in the target runtime unless a specific release documents a forwarding shim.
9. Retain the pinned legacy repository/bench for rollback until the populated cutover boundary is signed off.

Every patch needs a dry-run mode or audit report, batching for large sites, before/after row counts and monetary
control totals where applicable. Submitted records are never rewritten.

## Test and assurance status

Completed automated evidence is listed in `VALIDATION_AND_SIGNOFF.md`: target-only fresh install, 296 app tests,
deterministic E2E controls, repeated migration, PDF/browser/permission smoke checks and full target-only
backup/restore. The following remain required release gates:

- Populated upgrade from every supported legacy `za_local` version.
- Install order and missing-dependency failures for all downstream apps.
- Repeated migrate and uninstall/reinstall idempotency.
- Multi-company profile isolation and User Permission enforcement.
- Rate boundary, overlap, missing-pack and historical-resolution tests.
- Concurrent filing creation and DB uniqueness tests.
- Permission-denial tests for every whitelisted method.
- Scheduler retry/idempotency and missed-window tests.
- POPIA export/redaction and retention tests.
- Backup/restore checksum comparison.
- Practitioner review, parallel payroll/VAT periods, bank/SARS acceptance where claimed, and rollback rehearsal.

## Documentation ownership

Core owns the architecture, installation, compliance-profile, source-governance, filing-control, security,
backup/restore and troubleshooting guides. Domain apps publish their own practitioner pages into the shared guide
manifest. CI must reject broken links, duplicate routes and undocumented Production features.

## Exit criteria

These are release criteria, not a statement that production sign-off is complete:

- Core contains no downstream imports or domain calculations.
- All shared records and custom fields have exactly one owner.
- Historical rate resolution is deterministic and source-backed.
- Fresh and upgraded sites pass repeated migrate, backup and restore.
- No critical/high security or migration findings remain.
- Finance, payroll and workplace can be released independently against the same supported core version.
