# South African Localisation Multi-App Migration Programme

Status: complete. The suite consolidated to three apps in 2.0.0, with SA Labour and SA COIDA moving from
`za_local_workplace` into `za_local_payroll`.
Fresh E2E, repeated migration, target-only backup/restore and 296 app tests are recorded in
`VALIDATION_AND_SIGNOFF.md`. Production cutover still requires pinned release tags, populated legacy migration and
rollback rehearsal, parallel cycles, company-specific practitioner approval and external bank/authority acceptance
where claimed. This programme is not legal certification.

## Target repositories

| App | Runtime dependencies | Primary ownership |
|---|---|---|
| `za_local_core` | Frappe, ERPNext | Statutory sources, company compliance profile, obligations, filing evidence, shared security/setup/docs, and the SA VAT module absorbed from the retired `za_local_finance` in 2.0.0: VAT, commercial documents and accounting localisation. Corporate tax and CIPC remain roadmap scope. |
| `za_local_payroll` | Frappe, ERPNext, HRMS, core | SA employee/payroll foundation, PAYE/UIF/SDL/ETI, benefits, declarations, certificates and payroll payments. |
| `za_local_workplace` | Frappe, ERPNext, HRMS, core, payroll | BCEA/NMW, leave/termination entitlement, EE, skills/SETA, COIDA, injuries and workplace controls. |

Each app has an independent Git repository, semantic version, changelog, release notes, test workflow and owner.
The dependency graph is one-way; circular imports or optional reverse dependencies are prohibited.

## Architecture invariants

1. Every DocType, Custom Field, Property Setter, hook, route, workspace, report, print format and scheduler has
   exactly one owning app.
2. Cross-app access uses versioned services/events. Apps do not import another app's controllers or mutate its
   tables directly.
3. Business documents keep their existing names and SQL tables during extraction. Module ownership changes by
   migration; documents are not exported/deleted/reinserted.
4. A hook moves atomically: the new hook is enabled in the same release that the old hook is disabled.
5. Submitted payroll, tax, filing, payment and injury records are immutable. Corrections use amendments or separate
   adjustment/evidence records.
6. Statutory values are effective-dated and linked to an approved authority source. Historical calculations never
   use today's rates.
7. Missing mandatory statutory configuration fails before calculation or filing. It never silently returns zero,
   guesses a row or relies on a component label.
8. Domain preparation/submission is separate from core review/approval. `ZA Filing` records Draft, Reviewed and
   Approved; submitted receipt evidence derives Filed, Accepted or Rejected. Payment/bank acceptance remains a
   domain/external process and requires its own evidence.
9. Unsupported electronic formats remain `Controlled Manual` or `Preview`; generic exports are never represented
   as official filing files.
10. Security follows least privilege, Company/User Permissions and POPIA-sensitive field separation.

## Source ownership register

Before any move, generate a machine-readable `ownership_manifest.json` containing the current path/record name,
target app, migration patch, compatibility path, test owner and documentation owner. Minimum mapping:

| Existing area | Target owner |
|---|---|
| `sa_setup/doctype/za_local_setup`, shared help, API, compliance guide engine | Core |
| Generic Company/Address legal identity | Core |
| `sa_vat`, finance custom controllers, Chart of Accounts, commercial print formats | Finance |
| VAT/finance fields, reports, workspace, setup and tests | Finance |
| `sa_payroll`, payroll overrides, payroll calculation/export/payment utilities | Payroll |
| Employee/payroll/Salary Component/Salary Slip fields, payroll reports and formats | Payroll |
| `sa_labour`, `sa_coida`, leave/separation overrides and COIDA utilities | Workplace |
| BCEA/EE/skills/SETA/COIDA fields, reports, formats and schedulers | Workplace |
| Domain practitioner content | Owning domain; published through core |
| Legacy source inventory and rollback artifact | Existing `za_local`, retained separately until cutover approval |

The manifest must account for every tracked file and every installed database customization. CI rejects duplicate
owners, unowned artifacts and hooks registered by more than one installed app.

## Statutory authority baseline

The implementation team must maintain exact source versions in `ZA Statutory Source`, not rely on these general
landing pages alone:

- SARS employer/payroll guidance and the applicable PAYE/ETI/BRS documents:
  <https://www.sars.gov.za/guide-for-employers-in-respect-of-employees-tax-2027/>
- SARS VAT guides, including the applicable VAT 404 issue:
  <https://www.sars.gov.za/legal-counsel/legal-counsel-publications/find-a-guide/value-added-tax-vat/>
- Department of Employment and Labour Employment Equity publications:
  <https://www.labour.gov.za/publication-of-the-two-sets-of-employment-equity-regulations-following-the-commencement-of-the-ee-amendment-act-no-4-of-2>
- UIF employer declaration form/reference:
  <https://www.labour.gov.za/DocumentCenter/Forms/Unemployment%20Insurance%20Fund/Unemployment%20benefit%20forms/UI19_employers%20declarations.pdf>
- Compensation Fund employer obligations:
  <https://www.labour.gov.za/DocumentCenter/Pages/Compensation-Fund--obligations-of-the-employer-.aspx>
- Information Regulator POPIA/PAIA material: <https://inforegulator.org.za/popia/>
- CIPC company-compliance information: <https://www.cipc.co.za/?page_id=16055>

For each release, record title, issuing authority, publication/effective dates, version/issue, retrieved file,
checksum, affected rules, practitioner reviewer and approval. Values marked unverified in legacy JSON cannot enter
a Production rate pack.

## Programme workstreams and release controls

The bullets below include both implemented controls and remaining release/roadmap work. They are requirements, not
claims that every item is present in the current release.

### 1. Repository and dependency foundation

- Standardise Python/Node versions, `pyproject.toml`, lint/format rules and licence metadata.
- Add changelog, security policy, support matrix and deprecation policy to every repo.
- Pin compatible core/domain versions and test the complete version matrix.
- Use conventional, reviewable migrations; do not put recurring data mutation in `after_migrate`.
- Establish protected branches, required reviews, signed releases and supply-chain/dependency scanning.

### 2. Schema and data ownership

- Export current DocType metadata, Custom Fields, Property Setters, reports, formats, workspaces and fixtures.
- Compare source definitions with the live schema and code references.
- Create versioned patches for missing fields, invalid links, ownership/module changes and indexes.
- Transfer existing customization records in place, retaining their names, values and audit metadata.
- Add DB uniqueness for statutory identity where races would create invalid duplicates.
- Remove orphan records only in a later cleanup release after backup and reference checks.

### 3. Runtime ownership and compatibility

- Add compatibility modules at old import paths that issue deprecation logs and call the new public service.
- Add per-domain feature flags to run old, shadow or new behaviour; never both writing concurrently.
- Compare shadow outputs without changing documents.
- Move hooks by lifecycle group: validation, calculation, submission/cancellation, API, scheduler, report, assets.
- Remove migrate-time monkey patches and broad DOM/CSS selectors.
- Maintain compatibility for one major release and publish removal dates.

### 4. Statutory correctness

- Convert every number/code/formula into an effective-dated, source-backed rule or a tested algorithm referencing a
  source version.
- Build independent golden datasets reviewed by practitioners; do not derive expected values from production code.
- Add annual tax-year update and mid-year change workflows with expiring-source alerts.
- Create a capability matrix showing Production, Controlled Manual, Preview and Unsupported by version/company.

### 5. Security, privacy and auditability

- Inventory all whitelisted methods and test anonymous/low-role/authorised access.
- Apply Company and User Permissions to reports and aggregates.
- Separate payroll, tax IDs, bank details, disability, injury and medical records by permission level and purpose.
- Log sensitive exports and access without logging values themselves.
- Escape all Jinja/HTML output and validate all file/path inputs.
- Add maker/checker approval, immutable hashes and receipts for filings and bank files.
- Complete POPIA retention, access/export, correction and incident controls in core.

### 6. Performance and operations

- Remove database calls inside per-employee/per-component loops using cached maps/batches.
- Queue bulk certificates, guide publication, imports, reconciliation and workforce-wide checks on long queues.
- Make schedulers idempotent, window-based and persist notification state.
- Add structured logs, metrics, health checks and actionable Error Log entries with tracebacks.
- Prove backup, encrypted artifact retention, restore and rollback procedures.

### 7. Documentation and training

- Move practitioner content to its owner repo while publishing one coherent guide from core.
- Label legal sources, effective dates, assumptions, manual steps and unsupported features.
- Add implementation-consultant checklists, operator runbooks and troubleshooting decision trees.
- Build role-specific training for System Manager, payroll, finance, HR/EE/SDF and COIDA users.
- CI validates all links, routes, screenshots, examples, source versions and code field references.

## Migration waves

### Wave 0 — Baseline and freeze

Entry: existing `za_local` code and a representative test-site copy are available.

Actions:

- Tag the source release and back up database, public/private files, encryption key and site config.
- Capture row counts/checksums and monetary controls for payroll, GL, VAT, declarations and COIDA.
- Generate the ownership manifest and installed-schema diff.
- Classify every existing audit finding as confirmed, rejected with evidence, fixed, or planned.
- Freeze uncoordinated schema/statutory changes during migration.

Exit: reproducible baseline, restorable backup and signed control totals.

### Wave 1 — Core (target implementation complete; production approval pending)

- Install core with no downstream runtime hooks.
- Create compliance/source/obligation/filing/readiness records.
- Backfill company profiles and import source packs as unapproved until reviewed.
- Publish shared guide/setup/security services from core; do not depend on legacy compatibility routes.
- Run repeated migrate and restore tests.

Exit: core operates independently and has no HRMS imports. Legacy behavioural parity must be proven by the
populated upgrade rehearsal rather than assumed.

### Wave 2 — Finance (target implementation complete; two-period/practitioner sign-off pending)

- Transfer VAT/finance schema and print/report ownership.
- Shadow tax classification and VAT201 for historical/current periods.
- Reconcile source documents, VAT control accounts and returns.
- Cut over print formats, APIs, reports, calculation hooks and then return workflow.

Exit: two tax periods reconcile with no unexplained differences and practitioner/accounting sign-off.

### Wave 3 — Payroll (target implementation complete; parallel payroll/bank acceptance pending)

- Transfer payroll schema and import approved tax-year rules.
- Run historical golden tests and employee-level shadow comparisons.
- Parallel-run at least two monthly cycles and representative alternate frequencies.
- Cut over calculations, reports, declarations/certificates and payments in that order.

Exit: gross-to-net, GL, bank, EMP201, EMP501 and certificate controls reconcile; payroll sign-off recorded.

### Wave 4 — Workplace (target implementation complete; practitioner/regulatory review pending)

- Transfer labour/COIDA schema and restrict sensitive permissions first.
- Shadow BCEA warnings, EE/skills outputs and COIDA assessment.
- Validate payroll-to-workplace bases and termination payloads.
- Cut over workflows, reports, filings and scheduled obligations.

Exit: labour/EE/SDF/COIDA/privacy sign-offs and zero unexplained assessment/report differences.

### Wave 5 — Legacy retirement (not complete)

- Run two stable releases with telemetry showing no deprecated imports/routes.
- Take and restore a final pre-cleanup backup.
- Keep the legacy bench/runtime separate from the extracted target. Remove old hooks/source only through the
  populated, release-specific migration procedure.
- Keep a documented downgrade boundary; data created under the new model is not destructively downgraded.

Exit: `za_local` can be uninstalled without orphan Links, fields, formats, workspaces or broken imports.

## Test-data staging plan

Create a dedicated, non-production test fixture app or anonymised fixture package. Never commit real IDs, tax
numbers, bank accounts, medical data or credentials.

### Company matrix

- Monthly and bi-monthly VAT vendors; invoice/payment basis where supported.
- Payroll companies with monthly, weekly and fortnightly workers.
- Designated and non-designated employers.
- Different SETAs, bargaining/sector profiles and COIDA classes.
- ZAR base currency plus a foreign-currency transaction company.
- Companies with calendar, March-February and alternate financial years.

### Employee matrix

- Ages around rebate and ETI boundaries; citizen, resident, foreign national and incomplete-readiness records.
- Salaried, hourly/timesheet, commission, bonus and director scenarios.
- Mid-year joiners/leavers, unpaid leave, multiple assignments and off-cycle pay.
- Retirement, medical dependants, travel, vehicle, housing, loan, bursary and reimbursement combinations.
- ETI month 1/12/13/24/25, part-time hours, wage-floor and PAYE-cap cases.
- BCEA leave cycles, overtime/Sunday/public holiday work and termination reasons.
- EE/OFO/skills demographics represented with synthetic values.

### Finance matrix

- Full/abridged invoices around effective thresholds, ZAR and foreign currency.
- Standard, zero, exempt, out-of-scope, imported service, capital, mixed-use and blocked-input transactions.
- Credit/debit notes, bad debt/recovery, cancellation/amendment and late documents.
- VAT201, GL control, payment/refund and filing receipt evidence.

### Workplace matrix

- Injury with/without leave, claim, medical reports, workflow outcomes and access-role tests.
- COIDA per-employee cap and March-February assessment boundaries.
- WSP plan, training completions, ATR and SETA evidence.
- EE movement, promotion, termination, remuneration and small-cell privacy cases.

Fixtures must be deterministic, source-dated and self-cleaning. Expected outputs live in reviewed golden files with
independent calculation notes.

## CI/CD quality gates

Current repository CI runs Ruff lint/format, JSON/shell validation, a fresh target-only Frappe v16 app installation,
two migrations and server tests for the owning app. Core CI also compares the deterministic core-state fingerprint
and rejects a site containing legacy `za_local`.

The release pipeline must additionally run:

- JavaScript lint/format and any configured type checks not covered by repository CI.
- Full multi-app unit, integration, DocType lifecycle and permission suites.
- Fresh full-suite install and repeated `bench migrate`.
- Populated upgrade from the last two supported releases.
- Cross-app contract and dependency-boundary tests.
- Static scan for unknown field references, unsafe whitelisted methods, broad exception swallowing, `today()` in
  dated statutory calculations, unescaped template sinks and writes to submitted child records.
- Documentation/link/source-manifest validation.

Until those jobs are automated in hosted CI, retain manual/release evidence for the full end-to-end suite, browser
print/form tests, performance profiles, backup/restore, uninstall checks, dependency/security scans and supported
app-version matrix. Do not describe them as per-pull-request CI.

No release proceeds with failing tests, unresolved critical/high findings, unapproved statutory packs, unexplained
control-total differences or undocumented Production capabilities.

## Sign-off evidence pack

For each app/release retain:

- source/version and change-impact register;
- approved golden calculations and statutory form mappings;
- migration dry-run/output, schema diff and before/after control totals;
- test reports, performance results and security review;
- parallel-run/reconciliation evidence;
- backup/restore and rollback rehearsal;
- practitioner, process owner, privacy/security and technical approvals;
- known limitations and controlled-manual procedures.

“Compliant” is release-, date-, company-configuration- and process-dependent. The sign-off claim is therefore:
the specified features were tested against the recorded sources and controls for the supported period; it is not a
blanket legal certification or a substitute for the employer/vendor's statutory duties.

## Programme completion criteria

- All ownership-manifest entries are transferred and no duplicate hooks remain.
- All confirmed critical/high audit findings have regression tests and approved closure evidence.
- Core, finance, payroll and workplace install, migrate, back up, restore and release independently within the
  supported compatibility matrix.
- Finance, payroll and workplace end-to-end control totals reconcile with zero unexplained differences.
- Sensitive data permissions and export logging pass security/privacy review.
- Documentation matches the released code, rates, forms and capability labels.
- The old `za_local` app uninstalls cleanly after the supported compatibility window.
