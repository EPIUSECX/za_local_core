# Installation and migration

Installing is not configuring. Once the apps are on the site, work through
[Start Here: First-Run Setup](start-here) in order; this page covers only the bench and migration mechanics.

Then sign in and complete the **setup wizard in the browser** (country South Africa, time zone
Africa/Johannesburg, currency ZAR, financial year from 1 March). Do not script around it: completing the wizard
switches on the **Getting Started** setup checklists and runs the suite's setup hooks, which denominate the
workspace figures in rand. A site set up by script shows no checklists and keeps the installer's currency on its
workspace cards.

Install on Frappe v16 in dependency order. ERPNext is required by `za_local_core`. HRMS is required before
`za_local_payroll`. For the full suite, install ERPNext, HRMS, `za_local_core`, then `za_local_payroll`.
`za_local_core` installs without HRMS when payroll is not required, and gives VAT plus the governance foundation.

Sites running an earlier multi-app layout update both apps to 2.0.0 and migrate. Patches adopt the SA VAT, SA
Labour and SA COIDA modules and de-register `za_local_finance` and `za_local_workplace` without dropping schema or
records. Do not run `bench uninstall-app` on either retired app — that deletes the VAT201, labour, injury, claim
and COIDA history.

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

Core also prepares a Draft `ZA Statutory Rate Pack` for VAT so nobody has to hand-enter five rule keys. This is the
first configuration task on a new site: **South Africa VAT Settings cannot be saved until that pack and its source
are approved**, because there is no fallback rate. See
[Statutory Source Governance](../reference-operations/statutory-source-governance). Approval needs ZA Compliance
Reviewer or ZA Compliance Manager, and cannot be done by the account that installed the app, so plan for a named
reviewer rather than Administrator.

The old `za_local` app is a rollback source, not a compatibility runtime for the extracted apps. Do not archive or
uninstall it until the populated migration rehearsal, cutover boundary and separate rollback environment are approved.
