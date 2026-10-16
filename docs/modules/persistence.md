# persistence

Kind: **replaceable**. Package: `forge_rag.persistence`. Default: **on**.

Metadata, ACLs, jobs and vector storage.

## Contract and ownership

- Port: Repository.
- Configuration: `DATABASE_URL, SQLITE_MAX_CHUNKS`.
- Surface: All metadata/index operations.
- Data: rag_schema, rag_documents, rag_acl, rag_jobs, rag_chunks.

## Disable, replace or remove

Replace SQLRepository through the composition root; retain atomic enqueue/publication/deletion and authorization predicates. SQLite and PostgreSQL share contracts.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
