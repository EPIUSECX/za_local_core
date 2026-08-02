# SA Localisation Core

Shared statutory sources, rate packs, compliance profiles, filing controls, and audit foundations for South Africa.

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

The optional federated Wiki publisher combines documentation from all installed localisation apps. After installing Frappe Wiki, run:

```bash
bench --site $SITE_NAME execute za_local_core.practitioner_guide.stage.stage_space
```

It publishes `/sa-guide` and `/sa-user-guide`. CI validates ownership, content files, routes and relative links.

## Support and releases

See [SUPPORT.md](SUPPORT.md), [SECURITY.md](SECURITY.md), and
[CHANGELOG.md](CHANGELOG.md). A successful technical test run is not a substitute
for the external statutory and operational approvals in
[VALIDATION_AND_SIGNOFF.md](VALIDATION_AND_SIGNOFF.md).

## Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
bench get-app $URL_OF_THIS_REPO --branch main
bench --site $SITE_NAME install-app za_local_core
```

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

## License

MIT
