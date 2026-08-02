# Operations and troubleshooting

Before every release: back up the database, public/private files and encryption configuration; verify restore on an
isolated target-only site; run migrations twice; compare fingerprints, file hashes and control totals; build assets;
and run all app suites.

If a statutory calculation cannot resolve an approved rate or company-scoped master, stop the process and repair configuration. Do not enter guessed values to make payroll or a return submit.

External filing and payment evidence must include the authority/bank reference, timestamp, approved amount, attachment and checksum where available. Corrections use amendments or adjustment records; never rewrite submitted history.

Do not load legacy `za_local` and the extracted apps as concurrent runtime writers. Preserve legacy on a separate,
pinned rollback bench until the release-specific populated migration and rollback boundary are approved.

For support, retain the app versions, site version output, relevant document names, Error Log traceback, source version and control totals. Redact personal and banking values.
