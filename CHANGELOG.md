# Changelog

## 2.0.0 - 2026-08-03

### Absorbed SA Localisation Finance

The SA VAT module moved into this app from the separate `za_local_finance` app,
which is retired. The suite is now two apps: this one, and payroll and HR.

- VAT settings, supply classification, tax-invoice controls, VAT201 returns, the
  SA commercial print formats, VAT reports and the chart-of-accounts augmentation
  all ship here. The app is titled **SA Localisation Finance & Compliance**.
- Nothing was rewritten. The module name, DocType names, fieldnames and tables are
  unchanged, so no data is migrated or re-entered.
- `patches.v1_3.adopt_vat_module` re-points the SA VAT Module Def and Workspace to
  this app and de-registers `za_local_finance` using `remove_from_installed_apps`,
  never `remove_app` — an uninstall would have dropped every VAT201 return and
  tax-document record. It also removes the empty `SA Localisation Finance` module
  the retired app declared but never populated, and only when nothing references it.
- VAT setup lives in `sa_vat/install.py`, inside the module it configures.
- VAT stays inert until a company has South Africa VAT Settings, so a payroll-only
  site is unaffected by its presence.

### Fixed

- SA Labour and SA COIDA lost their Desk sidebar and desktop icons after the
  payroll merge in `za_local_payroll` 2.0.0. `WORKSPACE_SPECS` still attributed
  them to the retired `za_local_workplace`, and `get_available_workspaces` filters
  on the owning app being installed, so `_cleanup_stale_navigation` deleted their
  navigation entries while leaving the Workspace records intact. Both are now
  attributed to `za_local_payroll`, and a test asserts every shipped workspace
  names an app that actually declares its module.
- `LOCALISATION_APPS` keeps every app name the suite has shipped under, including
  retired ones. It is a cleanup allow-list, so dropping a retired name would leave
  that app's stale Desktop Icon on the site forever.

### Upgrading from 1.x

Update both apps and run `bench --site <site> migrate`. Do not run
`bench uninstall-app` on `za_local_finance` or `za_local_workplace`.

## 1.2.2 - 2026-08-03

- Documented the three-app suite. `za_local_workplace` is retired and its SA Labour
  and SA COIDA modules ship inside `za_local_payroll` from 2.0.0; the packaged
  guide pages and dependency tree now say so.

## 1.2.1 - 2026-08-03

- Fixed the guide status read failing with "Not permitted" on the Desk page.
  `frappe.call` defaults to POST while the endpoint is whitelisted `GET`, and
  Frappe reports that method mismatch as a permission error, which it is not. Both
  calls in the page now state their HTTP method, and a test asserts each stated
  method is one the endpoint allows.
- Reading guide status no longer requires a role. It reports `can_publish`, so the
  page hides its own publish button instead of offering an action that fails.
  Publication itself still requires System Manager.

## 1.2.0 - 2026-08-03

- Added a Desk entry point for the on-site guides: **SA Overview → Publish
  Localisation Guides** shows what each installed app contributes, whether Frappe
  Wiki is present and whether each space is up to date, and publishes on request.
  The whitelisted publish endpoint previously had no caller.
- Guide pages published into Frappe Wiki are now withdrawn on uninstall. Neither
  Wiki DocType has a module field, so `remove_app` could not reclaim them and they
  stayed live after the app that wrote them was gone.
- Publishing now converges: pages no installed app declares any more are
  withdrawn, and groups left empty are removed. Provenance is recorded per page so
  only pages this suite published are ever deleted.
- Uninstalling core removes the `/sa-guide` and `/sa-user-guide` spaces, unless a
  space also holds pages this suite did not publish. Deleting a Wiki Space
  cascades to its whole tree, so in that case only ours are withdrawn.
- Added a patch that force-reloads the SA Overview workspace, so the new card
  lands on sites where the stored record is newer than the shipped file.

## 1.1.0 - 2026-08-03

- Added workspace metrics: five number cards and three charts on SA Overview,
  seeded idempotently and fail-safe on a site with no data yet.
- Gave every workspace group its own icon instead of one shared list glyph.

## 1.0.0 - 2026-08-02

- Added `za_local_core.localisation` as the single owner of country scope; the
  suite now asks one question before enforcing any South African rule.
- Added `before_uninstall` to remove the `ZA Compliance` roles, which Frappe
  cannot reclaim by module, and documented the artefacts it deliberately keeps.
- Established the shared South African compliance, source-governance, privacy,
  readiness, filing-evidence and practitioner-guide foundation.
- Added deterministic multi-app ownership and hook audits.
- Added isolated compatibility, legacy-free E2E and cutover validation tooling.
- Made restored E2E fixtures self-healing for Frappe setup flags and added
  reproducible PDF, permission and control-total sign-off helpers.
- Added Frappe v16 CI, migration, backup/restore and release-gate documentation.
- Consolidated the extracted repositories behind one SA Localisation desktop app,
  a shared workspace switcher, and the original domain icon set.
- Corrected installation, cutover, validation and practitioner documentation to
  describe the target-only runtime, accountable roles, controlled-manual external
  filing and the boundary between automated evidence and human approval.

Release tags must pin compatible versions of all four localisation apps.
