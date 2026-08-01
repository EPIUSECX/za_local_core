# Migration Baselines

Generated baseline files contain non-personal row counts, monetary control totals, installed apps and module
ownership captured before and after migration. They must never contain employee, customer, tax, identity or bank
details.

Regenerate a site baseline with:

```bash
bench --site SITE execute za_local_core.migration.baseline.collect
```

Review and commit only approved test-site baselines. Production baselines belong in the restricted migration
evidence store, not Git.
