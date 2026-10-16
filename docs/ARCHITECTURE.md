# Architecture

The business backend owns accounts, sessions and organization membership. This
service owns documents, evidence indexes and ingestion jobs. Both Modular Forge
backends consume the same HTTP contract; neither has to embed Python RAG code or
share its account database with the service.

## Trust boundaries

The backend first validates the current account through its existing auth path,
then resolves immutable subject, tenant and groups from its own records. A
separate key signs a 60-second HS256 delegation for the RAG audience. RAG verifies
issuer-specific key, algorithm, token type, required claims, timestamps, lifetime
and scopes. Claims from end-user access tokens are not accepted directly. The
integration proxies mint the least read/write scope needed for each request.
Revocation or membership changes can take up to the remaining 60-second lifetime
of an already-issued delegation to propagate; tokens are not one-time tickets.

The default integrations isolate each account in its own tenant. An organization
deployment replaces the identity resolver with server-side membership lookup.
Canonical tenants can span the two backends, while subject ACLs use
`issuer:subject` so Python and Java numeric IDs never collide. Sharing a tenant
does not bypass the per-document owner/subject/group ACL.

## Ingestion

1. Validate size, content type, document key and ACL. Plain/Markdown are UTF-8;
   PDF is Base64 and opt-in. No network fetch is triggered by a URL in a document.
2. Atomically persist document revision, ACL and durable job in one DB transaction.
   `Idempotency-Key` is unique per tenant/actor, across datasets. A repeated identical
   request returns its job; a different payload/signature with that key returns 409.
3. A worker claims a job using conditional update; PostgreSQL adds `SKIP LOCKED`.
   A renewable lease and fencing token prevent expired workers publishing results.
4. Extract text, split bounded overlapping character chunks, preserve page and
   normalized-text offsets, and batch embeddings (32 inputs/request). Provider
   dimensions, finite values and nonzero vectors are checked.
5. Commit all chunks, the active revision and job completion atomically. Clear the
   job's raw payload. A newer revision or deletion invalidates the old worker.

Updates hide the previous active revision immediately. This deliberately pauses
retrieval for that document until replacement succeeds, avoiding exposure of old
content under new permissions. Failed updates stay hidden. Retry a terminal
failure by submitting the source again with a new idempotency key. Existing
chunks are replaced at successful publication or removed by explicit deletion.

Transient errors retry with exponential delay, up to the configured attempt
limit. Invalid documents and pipeline configuration mismatch fail permanently.
Terminal jobs retain codes and digests, never parser/provider diagnostic text or
raw payload. A process crash leaves a lease that another worker can reclaim.
This is at-least-once processing; provider calls may be billed again after a crash.

## Retrieval and generation

Tenant, dataset, current revision, pipeline signature, and owner/subject/group
authorization are applied to the SQL query **before** either candidate limit.
PostgreSQL performs exact pgvector cosine ranking and `simple` full-text ranking;
SQLite performs bounded exact cosine and BM25 in memory on authorized rows only.
Both combine ranks using reciprocal rank fusion with constant 60. A small EN/TR
stop-word list only affects the lexical query; it is not linguistic stemming.

Semantic similarity or a positive lexical match admits evidence; a fixed
threshold is a configurable heuristic, not calibrated confidence. Optional
lexical reranking demonstrates the port; a production cross-encoder can replace
it. Top-k and the context character budget limit what leaves the service.

The generator sees untrusted evidence and a question, with separate instructions,
no tool access, and a structured statements/citation-ID contract. Unknown citation
IDs are rejected. Access/current revision is rechecked after generation; if the
context changed, the response is withheld with 409. Each statement carries its
chunk IDs, and citations include revision, page, offsets and excerpt. Empty
evidence or an empty generated statement list returns `insufficient_evidence`.

Citation membership proves provenance, not factual entailment. An LLM can still
misread a valid source or obey a malicious document. Domain-specific factual and
prompt-injection evals remain necessary. If deletion happens after evidence was
sent to an external provider, the service cannot retract that provider request.

## Storage and scale

`rag_documents` owns metadata/current revision; `rag_acl` owns readers;
`rag_jobs` owns durable work; `rag_chunks` owns text, provenance and vectors.
Versioned migrations are explicit CLI operations, not startup side effects.

All storage lives in one database, so publication/deletion are transactional.
No Redis broker/vector DB dual-write race is introduced. SQLite is for a small
single-machine demo and enforces an authorized-corpus scan limit. PostgreSQL exact
vector search prioritizes correctness over ANN throughput. Large deployments can
replace the repository port with indexed pgvector/Qdrant adapters; preserve ACL
pre-filtering, overfetch/recall analysis, and a durable indexing outbox.

The pipeline signature includes extractor version/PDF mode, chunk settings,
embedding provider/model/dimensions and `EMBEDDING_REVISION`. Queries never mix
incompatible indexes. A model alias changing its weights is not detectable by
name alone: increment `EMBEDDING_REVISION` and reingest with fresh idempotency keys.
Changing only the generator does not require re-embedding.

No conversation persistence, shared answer cache or history rewriting is enabled.
Add these behind ports with tenant/ACL-aware keys and deletion invalidation.
Streaming must preserve citation checks and handle revocation; do not simply
forward raw unvalidated provider tokens to clients.
