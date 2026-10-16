# reranking

Kind: **optional**. Package: `forge_rag.reranking`. Default: **off**.

Replaceable candidate reranker.

## Contract and ownership

- Port: Reranker.
- Configuration: `MODULE_RERANKING_ENABLED`.
- Surface: Candidate ordering only.
- Data: No tables.

## Disable, replace or remove

Off by default; disables adapter import. Delete conditional branch and package to remove. Lexical adapter is a deterministic example, not a cross-encoder.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
