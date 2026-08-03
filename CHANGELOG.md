# Changelog

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
