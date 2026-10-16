# Operations

## Dependency maintenance

Dependabot version-update configuration is intentionally absent, and automatic
security-update pull requests are disabled in repository settings. Dependency
changes are reviewed and applied manually. The scheduled dependency audit and
CodeQL workflows continue to run independently of Dependabot.

When changing Python dependencies, update and commit `uv.lock`, then run the
verification and audit commands in [README](../README.md#modules-and-verification).
For Docker or Maven updates, also run the container and backend integration
checks. Compare the actual dependency changes and test current branches before
merging; an old failed run may predate a fix already present on `main`.

## Local processes

Run `forge-rag init-env`, then `forge-rag migrate`. Startup never auto-creates
tables. Start the API on port 8090 and a separate `forge-rag worker` process.
`worker --once` consumes at most one currently available job; it does not wait
for future retry delays. SIGINT/SIGTERM stop the loop after the active job.
`demo` and `evaluate` use their own in-memory SQLite database, regardless of
your configured provider/database, and only public fixture text.

`docker compose up --build` starts private PostgreSQL + pgvector, a one-shot
migration, API and worker. The API binds only `127.0.0.1:8090`; DB ports are not
published. Compose is a local demonstration, with offline providers by default.
The password and delegation map come from the generated `.env`. Containers run
as a non-root user; worker CPU/memory are bounded. Pin image digests in your
deployment's dependency maintenance process.

## Production checklist

- Use `ENVIRONMENT=production`, PostgreSQL/pgvector, explicit `ALLOWED_HOSTS`,
  `MODULE_API_DOCS_ENABLED=false`, and private backend-specific keys. Provision
  the `vector` extension with a migration role; runtime DB credentials should
  have only the required table permissions. Use TLS with certificate verification
  (`sslmode=verify-full` and a trusted CA) for remote PostgreSQL.
- Put the API behind internal TLS/network policy. Browser/mobile clients go
  through the existing business backend. Set HTTP body, timeout, concurrency,
  per-user/tenant request, queued-job, storage and model-spend quotas there.
  There is no built-in distributed quota or billing ledger in this starter.
- Keep API/worker pipeline settings identical; deploy coordinated model changes.
  Use PostgreSQL for multiple workers. Workers heartbeat their lease and commits
  are fenced; a crash can still cause duplicate provider billing before publication.
- Run untrusted extraction in isolated resource-limited worker containers, with
  restricted outbound access. PDF decompression/parsing can allocate memory
  before a post-decompression check; limits in application code are not a sandbox.
- Monitor ready status, queued-job age, failed jobs, provider latency/token usage,
  saturation and deletion requests. `/health/ready` validates database/schema,
  not a paid provider's health. Logs expose request IDs, status and elapsed time;
  they do not record prompts/documents/answers. Add your OTEL/metrics exporter as
  an adapter if needed. No public metrics endpoint is installed.
- Back up PostgreSQL with encryption and tested restore procedures. Treat vector
  indexes and text chunks as sensitive as source documents. Deletion from live
  tables does not remove copies from WAL/backups or external provider history;
  define retention and restoration rules accordingly.

## Retry, retention and reindexing

Transient processing failures retry exponentially (2, 4, ... seconds) up to
`JOB_MAX_ATTEMPTS`; jobs then become `failed`. The raw payload is scrubbed on
completion, terminal failure, supersession and deletion. A crash keeps it until
the lease is reclaimed and processing reaches a terminal state. An expired
worker cannot publish; renewable leases allow slow jobs without duplicate claims.

`forge-rag purge-jobs --days 30` removes terminal metadata older than the chosen
period. Schedule it externally. This also expires the idempotency guarantee for
those keys; use immutable event/version IDs and source version checks in your
business system if you need guarantees beyond retention. Source document metadata
and chunks are not removed by job retention.

Reindex by sending each authoritative source again with its stable `external_id`
and a new version-specific idempotency key. Updates hide old evidence until ready.
There is no retained raw-document object store after successful processing; keep
original files in your business storage (for example R2) and resubmit them. RAG
never fetches arbitrary user-supplied URLs. Large object-store imports should use
an allowlisted connector and durable source-event/outbox workflow.

Rotating delegation keys requires updating the RAG issuer map and the relevant
backend together. This version has one active key per issuer and no `kid` overlap
window; plan a brief coordinated rotation or extend the verifier with versioned
keys. Already-issued tokens are valid at most 60 seconds if the old key remains.

## Schema migrations and capacity

`persistence/migrations/v0001.py` is the frozen initial schema. Future releases
must add explicit numbered migration steps and update the schema-version check;
do not change the released migration. Take a backup before a schema upgrade.
Initial migrations are serialized with a PostgreSQL advisory transaction lock.

SQLite scans only the authorized corpus, bounded by `SQLITE_MAX_CHUNKS`; overflow
returns 503 instead of silently dropping relevant documents. PostgreSQL uses exact
vector search and full-text ranking, without ANN/HNSW tuning. Profile on your
corpus before choosing ANN indexes; preserve authorization and recall semantics.
