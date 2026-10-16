# retrieval

Kind: **required**. Package: `forge_rag.retrieval`. Default: **on**.

Authorized hybrid retrieval and grounded query API.

## Contract and ownership

- Port: QueryService, Repository, Embedder, Generator, optional Reranker.
- Configuration: `CANDIDATE_LIMIT, MIN_SIMILARITY, MAX_CONTEXT_CHARS`.
- Surface: POST /v1/search and /v1/query.
- Data: No new tables; authorized evidence access.

## Disable, replace or remove

Required. Preserve SQL pre-filtering, no-evidence behavior, citation validation and post-generation access check. Tune thresholds with real domain evals.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
