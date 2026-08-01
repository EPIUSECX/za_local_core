# Multi-app cutover and rollback runbook

Use this only after change approval and a tested maintenance window. Replace placeholders with explicit site names; never run restore or destructive commands against an unresolved variable.

## 1. Pre-cutover

1. Freeze payroll, finance and localisation configuration changes.
2. Record `bench version`, installed app versions and active feature-owner settings.
3. Capture control totals using the approved baseline script.
4. Back up database and files:

   ```bash
   bench --site <source-site> backup --with-files
   ```

5. Copy the backup plus encryption configuration to approved protected storage and verify file hashes.

## 2. Rehearse on an isolated restore target

1. Confirm the exact target site and take its own backup.
2. Use a clean restore target, or quarantine any pre-existing target files before
   restoring. Frappe overlays file archives and does not remove unrelated files.
3. Restore the source database, public files and private files using explicit backup paths.
4. Install apps in order: core, finance, payroll, workplace.
5. Run migration twice.
6. Enable dedicated runtime ownership and clear caches.
7. Run the hook audit, all app tests, E2E stages and control-total comparison.
8. Compare database controls and the relative-path/content hashes of public and
   private files, excluding backup directories.
9. Build assets and perform browser/PDF/role smoke tests.

Do not proceed if any row count, amount, hash, permission or rendered statutory field differs without a documented and approved explanation.

## 3. Production cutover

1. Repeat the final backup and hash verification.
2. Deploy pinned, approved tags for all four apps.
3. Install/migrate in dependency order.
4. Enable dedicated runtime ownership once; never leave legacy and dedicated writers active together.
5. Clear cache, restart workers/web, build assets and run read-only health/control checks.
6. Release the site only after the technical and process owners sign the cutover record.

## 4. Rollback

Rollback is permitted only within the approved data boundary. Stop writes, preserve failure logs/evidence, restore the pre-cutover database and files, deploy the previous app versions, migrate, restart and compare the original controls. Do not attempt a code-only downgrade after new-schema business documents have been created unless the release-specific rollback assessment explicitly approves it.

## 5. Evidence retention

Retain backup hashes, app versions, command logs, schema/hook audits, before/after controls, test outputs, screenshots/PDF samples, external acceptance evidence, approvals, deviations and the final go/no-go decision.
