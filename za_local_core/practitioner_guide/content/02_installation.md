# Installation and migration

Install in dependency order: ERPNext, HRMS, `za_local_core`, `za_local_finance`, `za_local_payroll`, then `za_local_workplace`. Finance does not require HRMS, but the full suite does.

Before migrating from legacy `za_local`:

1. Back up the database, public files, private files and encryption configuration.
2. Capture payroll, declaration, VAT, COIDA and GL control totals.
3. Install all target apps and run `bench --site <site> migrate`.
4. Run the hook-ownership audit and confirm one writer per critical hook.
5. Run the documented end-to-end and restore rehearsals on a disposable site.
6. Obtain payroll, finance, workplace/privacy and technical approval before production cutover.

Never uninstall the compatibility app before the migration release’s rollback boundary has been approved.
