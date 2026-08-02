# SA Localisation Core

Shared statutory sources, rate packs, compliance profiles, filing controls, and audit foundations for South Africa.

This app provides governance and evidence controls. It is not a legal certification, does not make an employer or
vendor compliant by installation alone, and does not submit returns to SARS or another authority.

See the [migration plan](MIGRATION_PLAN.md) for the source ownership, new compliance model, migration sequence and
release gates.

See also the [multi-app migration programme](MULTI_APP_MIGRATION_PROGRAMME.md) for sequencing, test data,
cutover, rollback and sign-off across all four repositories.

Current test evidence and remaining release gates are recorded in [VALIDATION_AND_SIGNOFF.md](VALIDATION_AND_SIGNOFF.md). Use [CUTOVER_RUNBOOK.md](CUTOVER_RUNBOOK.md) for backup, migration, validation and rollback.

## Unified Desk experience

`za_local_core` owns the single **SA Localisation** desktop entry. It discovers the installed localisation extensions and presents their workspaces together under one launcher and workspace switcher:

- SA Overview
- SA Payroll
- SA VAT
- SA Labour
- SA COIDA

The finance, payroll and workplace apps do not add separate desktop applications. Their install, migrate and uninstall hooks ask core to refresh the shared navigation, so the launcher reflects only the localisation areas available on the site. The icon assets are packaged by core and remain consistent across the desktop launcher and workspace headers.

The optional federated Wiki publisher combines documentation from all installed localisation apps. A System
Manager can publish it from the localisation setup UI. A bench administrator may run the same idempotent publisher
directly after installing Frappe Wiki:

```bash
bench --site <site> execute za_local_core.practitioner_guide.stage.stage_space
```

It publishes `/sa-guide` and `/sa-user-guide`. CI validates ownership, content files, routes and relative links.

## Support and releases

See [SUPPORT.md](SUPPORT.md), [SECURITY.md](SECURITY.md), and
[CHANGELOG.md](CHANGELOG.md). A successful technical test run is not a substitute
for the external statutory and operational approvals in
[VALIDATION_AND_SIGNOFF.md](VALIDATION_AND_SIGNOFF.md).

## Installation

Install on a Frappe v16 bench after ERPNext. A full-suite target must use this dependency order:

1. Frappe and ERPNext
2. HRMS, when payroll or workplace is required
3. `za_local_core`
4. `za_local_finance`
5. `za_local_payroll`
6. `za_local_workplace`

Install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
bench get-app <core-repository-url> --branch main
bench --site <site> install-app za_local_core
```

Do not install the extracted apps as active writers on a site or bench that still runs the legacy `za_local`
monolith. The release gate rejects legacy `za_local` on a target-only candidate. Rehearse a populated legacy
upgrade on an isolated clone, retain a separate rollback environment, and follow [CUTOVER_RUNBOOK.md](CUTOVER_RUNBOOK.md).

## Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/za_local_core
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

## Uninstalling

`bench uninstall-app` removes this suite's DocTypes and every schema
customisation it owns: Custom Fields, Property Setters, Print Formats and
Workspaces all carry an owning module, and `za_local_core` additionally removes
the `ZA Compliance` roles, which Frappe cannot reclaim by module.

Business and audit records are deliberately retained. Salary Components,
Payroll Periods, Income Tax Slabs, approved statutory sources, rate packs,
filings and submission receipts are a company's payroll and compliance history,
not app schema. Remove them only through a reviewed data decision.

## License

MIT
