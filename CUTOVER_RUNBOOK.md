# Multi-app cutover and rollback runbook

Use this only after change approval and a tested maintenance window. Replace placeholders with explicit site names;
never run restore or destructive commands against an unresolved variable.

This runbook defines the control boundary; it is not evidence that a populated legacy upgrade has passed. The
2 August 2026 automated evidence covers a fresh target-only site and a full restore of that target-only candidate.
Before migrating a customer site from legacy `za_local`, rehearse the release-specific data transition on a
disposable copy and approve every difference.

## 1. Pre-cutover

1. Freeze payroll, finance and localisation configuration changes.
2. Record `bench version`, installed app versions and active feature-owner settings.
3. Capture control totals using the approved baseline script.
4. Back up database and files:

   ```bash
   bench --site <source-site> backup --with-files
   ```

5. Copy the backup plus encryption configuration to approved protected storage and verify file hashes.
6. Preserve a separately deployable rollback bench containing the pinned legacy app and dependencies. Do not rely
   on keeping legacy and extracted localisation controllers active in one target runtime.

## 2. Rehearse on an isolated restore target

1. Confirm the exact target site and take its own backup.
2. Use a clean restore target, or quarantine any pre-existing target files before
   restoring. Frappe overlays file archives and does not remove unrelated files.
3. Restore the source database, public files and private files using explicit backup paths.
4. Apply only the approved release-specific legacy-to-target data transition. A generic `install-app --force` is
   not an approved migration procedure.
5. Ensure the target runtime does not load legacy `za_local`, then install in dependency order: core, finance,
   payroll and workplace; HRMS must already be installed before payroll/workplace.
6. Run migration twice and compare the deterministic core-state fingerprint.
7. Clear caches, rebuild assets and restart web, scheduler and workers.
8. Run the legacy-absence gate, hook audit, all app tests, E2E stages and control-total comparison.
9. Compare database controls and the relative-path/content hashes of public and
   private files, excluding backup directories.
10. Perform browser/PDF/role smoke tests and verify the intended Company/User Permissions.

Do not proceed if any row count, amount, hash, permission or rendered statutory field differs without a documented and approved explanation.

## 3. Production cutover

1. Repeat the final backup and hash verification.
2. Deploy pinned, approved tags for every app in the suite.
3. Apply the exact migration procedure proven on the populated rehearsal, then install/migrate in dependency order.
4. Activate the extracted runtime once; never leave legacy and dedicated writers active together.
5. Clear cache, restart workers/web, build assets and run read-only health/control checks.
6. Release the site only after the technical and process owners sign the cutover record.

## 4. Rollback

Rollback is permitted only within the approved data boundary. Stop writes, preserve failure logs/evidence, restore
the pre-cutover database and files on the pinned rollback bench, deploy the previous app versions, migrate, restart
and compare the original controls. Do not attempt a code-only downgrade after new-schema business documents have
been created unless the release-specific rollback assessment explicitly approves it.

## 5. Evidence retention

Retain backup hashes, app versions, command logs, schema/hook audits, before/after controls, test outputs, screenshots/PDF samples, external acceptance evidence, approvals, deviations and the final go/no-go decision.
