# SA Localisation Core Migration Plan

Status: architecture and migration specification; no production ownership has moved yet.

## Purpose

`za_local_core` owns shared South African compliance infrastructure. It must not contain VAT calculations,
payroll calculations, labour rules, or COIDA transaction logic. Domain apps consume its stable public services.

## Dependency contract

```text
frappe -> erpnext -> za_local_core
                         |-> za_local_finance
                         |-> hrms -> za_local_payroll -> za_local_workplace
```

The core app knows nothing about downstream apps. It publishes services and document events; it does not import
finance, payroll, or workplace modules. The existing `za_local` app remains the compatibility and migration
orchestrator until all ownership transfers are complete.

## Existing source to move

| Current source in `za_local` | Destination | Treatment |
|---|---|---|
| `za_local/sa_localisation/` | `za_local_core/sa_localisation/` | Move the shared module identity only. |
| `za_local/api/` | `za_local_core/api/` | Move app-access and shared health APIs; enforce permissions on every endpoint. |
| `za_local/utils/file_utils.py` | `za_local_core/files.py` | Move safe app-resource resolution and traversal protection. |
| `za_local/utils/setup_utils.py` | `za_local_core/setup/` | Split into small idempotent setup services. |
| `za_local/sa_setup/doctype/za_local_setup/` | `za_local_core/` | Replace the monolithic setup document with a compliance-profile-driven setup coordinator while retaining a compatibility route. |
| `za_local/sa_setup/page/sa_local_help/` | `za_local_core/` | Convert into the combined product help/health page. |
| `za_local/sa_setup/workspace/sa_localisation/` | `za_local_core/` | Own the single product overview workspace. |
| `za_local/practitioner_guide/manifest.py` and `stage.py` | `za_local_core/practitioner_guide/` | Keep the guide publication engine in core; domain content moves to its owner app. |
| `za_local/public/js/za_local_feedback.js` | `za_local_core/public/js/` | Retain only shared feedback/error behaviour. |
| Shared shell styles/icons from `za_local/public/` | `za_local_core/public/` | Move brand assets and shared design tokens; domain CSS stays with the domain. |
| Shared portions of `za_local/tasks.py` | `za_local_core/tasks.py` | Keep compliance-calendar and source-expiry checks only. |
| `za_local/sa_setup/statutory_setup.py` | `za_local_core/setup/` | Retain company-profile orchestration; move payroll/VAT-specific seeds to downstream apps. |
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
| `ZA Filing` | Company/period instance of an obligation and its internal working paper. | Draft, Reviewed, Approved, Filed, Rejected, Amended. |
| `ZA Submission Receipt` | External reference, timestamp, declared amount, attachment and checksum. | Immutable evidence record. |
| `ZA Feature Readiness` | States whether a feature is Production, Controlled Manual, Preview or Unsupported. | System-managed from installed apps and configuration. |
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
2. Install core alongside `za_local`; do not duplicate hooks or custom fields.
3. Create core DocTypes and backfill compliance profiles from existing Company fields.
4. Import statutory JSON packs as immutable records while preserving their original checksums.
5. Move guide publication and shared setup UI behind compatibility APIs.
6. Transfer field ownership without deleting/recreating Custom Field rows.
7. Replace `after_migrate` data mutation with ordered, idempotent patches.
8. Keep old Python paths as deprecated forwarding modules for one major release.
9. Remove compatibility code only after two successful release cycles.

Every patch needs a dry-run mode or audit report, batching for large sites, before/after row counts and monetary
control totals where applicable. Submitted records are never rewritten.

## Test plan

- Fresh install with ERPNext only.
- Install order and missing-dependency failures for all downstream apps.
- Upgrade from each supported `za_local` version using a populated database.
- Repeated migrate and uninstall/reinstall idempotency.
- Multi-company profile isolation and User Permission enforcement.
- Rate boundary, overlap, missing-pack and historical-resolution tests.
- Concurrent filing creation and DB uniqueness tests.
- Permission-denial tests for every whitelisted method.
- Scheduler retry/idempotency and missed-window tests.
- POPIA export/redaction and retention tests.
- Backup/restore checksum comparison.

## Documentation ownership

Core owns the architecture, installation, compliance-profile, source-governance, filing-control, security,
backup/restore and troubleshooting guides. Domain apps publish their own practitioner pages into the shared guide
manifest. CI must reject broken links, duplicate routes and undocumented Production features.

## Exit criteria

- Core contains no downstream imports or domain calculations.
- All shared records and custom fields have exactly one owner.
- Historical rate resolution is deterministic and source-backed.
- Fresh and upgraded sites pass repeated migrate, backup and restore.
- No critical/high security or migration findings remain.
- Finance, payroll and workplace can be released independently against the same supported core version.

