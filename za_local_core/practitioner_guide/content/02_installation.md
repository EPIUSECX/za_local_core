# Installation and migration

Install on Frappe v16 in dependency order. ERPNext is required by core and finance. HRMS is required before payroll
or workplace. For the full suite, install ERPNext, HRMS, `za_local_core`, `za_local_finance`, `za_local_payroll`,
then `za_local_workplace`. Finance can be installed without HRMS when payroll/workplace are not required.

Before migrating from legacy `za_local`:

1. Back up the database, public files, private files and encryption configuration.
2. Capture payroll, declaration, VAT, COIDA and GL control totals.
3. Restore a copy to a separate target-only bench/site and apply the release-specific migration procedure. Do not
   use an ad-hoc `install-app --force` or keep legacy and extracted runtime writers active together.
4. Install all target apps and run `bench --site <site> migrate` twice.
5. Run the legacy-absence and hook-ownership audits and confirm one writer per critical hook.
6. Run the documented end-to-end, populated-upgrade, backup/restore and rollback rehearsals on disposable sites.
7. Obtain payroll, finance, workplace/privacy and technical approval before production cutover.

Core seeds official-source catalog metadata and disabled company profiles as Draft records only. Upload the exact
private source/evidence files, verify their checksums and complete maker/checker approval before downstream apps
use a rate pack or company profile. Never convert Draft catalog rows to Approved merely to unblock a test.

The old `za_local` app is a rollback source, not a compatibility runtime for the extracted apps. Do not archive or
uninstall it until the populated migration rehearsal, cutover boundary and separate rollback environment are approved.
