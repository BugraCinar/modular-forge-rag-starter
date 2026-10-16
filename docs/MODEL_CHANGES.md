# Changing an indexing model or pipeline

An embedding/indexing change is a data operation as well as a configuration
change. The service stores processed evidence after successful ingestion; keep
authoritative source files in the business application's storage for reindexing.

## Decide whether reindexing is needed

| Change | Reindex existing sources? |
|---|---|
| Embedding provider, model or dimensions | Yes. |
| Embedding weights behind an unchanged alias | Yes; increment `EMBEDDING_REVISION`. |
| Chunk size/overlap or extractor implementation | Yes; update the implementation signature when appropriate. |
| PDF toggle | Yes for matching the new pipeline signature, including text sources. |
| Generator model only | No; existing evidence vectors remain compatible. |
| Reranker or admission threshold | No vector rebuild; evaluate query quality before rollout. |

## Coordinated rollout

1. Record the current configuration and source/event versions. Back up the index
   and prepare a representative evaluation set for the new pipeline.
2. Pause new ingestion at the business backend and let active jobs finish before
   replacing worker/API configuration. Do not leave old and new workers competing
   for the same queue with incompatible signatures.
3. Deploy the same embedding/chunking/extraction settings to API and workers.
   Incompatible queued jobs fail with `pipeline_changed` and need resubmission.
4. Resubmit each authoritative source with its stable `external_id`/dataset and
   a new version-specific idempotency key. Preserve the intended ACL and owner.
5. Wait for job completion, inspect failures and verify authorized retrieval,
   unanswerable questions and citation behavior before resuming normal ingestion.

Queries do not mix pipeline signatures. Old evidence can disappear from search
as soon as the API switches configuration; each document update also hides its
previous revision until the replacement is ready. Plan a maintenance window or
a separately designed parallel-index rollout if uninterrupted retrieval is needed.

## Rollback and failed documents

Changing configuration back does not reconstruct vectors replaced by completed
reindex jobs. Resubmit sources using the previous pipeline and fresh idempotency
keys, or use your tested database restore procedure. Keep source ownership and
membership mappings consistent during either path.

A terminal failed job has its raw payload scrubbed. Resubmit the authoritative
source with a new key after correcting the problem; replaying the old key returns
the existing job. See [operations](OPERATIONS.md) for retries/retention and
[evaluation](EVALUATION.md) for quality checks.
