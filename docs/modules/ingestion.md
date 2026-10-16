# ingestion

Kind: **optional**. Package: `forge_rag.ingestion`. Default: **on**.

Document API and durable worker.

## Contract and ownership

- Port: IngestionService and Worker consume Extractor/Chunker/Embedder/Repository.
- Configuration: `MODULE_INGESTION_ENABLED, MAX_DOCUMENT_BYTES, MAX_CHUNKS, JOB_LEASE_SECONDS, JOB_MAX_ATTEMPTS`.
- Surface: POST/GET/DELETE /v1/documents; GET /v1/jobs; worker CLI.
- Data: Document, ACL and durable-job lifecycle; chunks published through Repository.

## Disable, replace or remove

Disable removes all document/job routes and worker CLI. Query can still read an existing index. Remove conditional composition and package; retain independent chunking and shared models. Data removal needs an explicit migration.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
