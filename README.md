# SA Localisation Core

Shared statutory sources, rate packs, compliance profiles, filing controls, and audit foundations for South Africa.

See the [migration plan](MIGRATION_PLAN.md) for the source ownership, new compliance model, migration sequence and
release gates.

See also the [multi-app migration programme](MULTI_APP_MIGRATION_PROGRAMME.md) for sequencing, test data,
cutover, rollback and sign-off across all four repositories.

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
