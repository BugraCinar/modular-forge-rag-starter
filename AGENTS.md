# Repository guide

Read docs/MODULAR_PLAN.md and the module guide before changing a module.
Core services depend on shared ports, never on provider implementations. Only the
composition root selects adapters. Disabled modules must not install routes or
import optional dependencies. Keep the module catalog, settings and docs aligned.

Tenant and subject come from a verified backend delegation, never a request body.
Filter tenant, dataset, current revision, embedding signature and document ACL
before candidate selection. Preserve job lease fencing and atomic publication.
Never log documents, questions, answers, keys or bearer tokens. Keep migrations
immutable after release. Do not make paid provider calls in tests or CI.

Run ruff check/format, mypy src, pytest, offline evaluation, pip-audit and build.
PostgreSQL contracts and Java integration tests run in CI as well.
