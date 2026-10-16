# Contributing

Read [the modular plan](docs/MODULAR_PLAN.md) and the affected
[module guide](docs/modules/) first. Core services consume shared ports; the
composition root selects concrete providers. Keep optional dependencies and
routes absent when their module is disabled.

## Setup and verification

Use `uv sync --frozen --all-extras`, then run the verification commands in
[README](README.md#modules-and-verification). The default tests and offline eval
use synthetic data and make no paid model calls. Live provider behavior must not
be a prerequisite for a pull request's tests.

For gateway changes, also run the [integration checks](docs/INTEGRATION_TESTING.md).
PostgreSQL contracts need a disposable database. Java tests require Java 21;
the Maven wrapper downloads the configured Maven distribution.

## Compatibility

Keep tenant, dataset, current revision, embedding signature and ACL predicates
ahead of retrieval limits. Preserve renewable lease fencing and atomic
publication/deletion. Provider changes need mock contract tests; indexing changes
may require a new pipeline signature and a documented reindex procedure.

New optional modules need a toggle, catalog entry, dependency ownership and
removal instructions. Released schema migrations are immutable. Dependency
changes need a lockfile update and fresh audit. Describe any impact on existing
documents, job retries or client JSON in the pull request.

Documentation changes should have working local links and commands consistent
with the implementation. Runtime tests need not be added for prose-only edits.
Keep source documents, questions, answers, service keys and bearer tokens out of
public issues and diagnostics. Use [the security policy](SECURITY.md) for private
vulnerability reports.
